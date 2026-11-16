"""AI adapter — picks a provider and returns one structured AiResponse (FR-08/FR-19).

Provider selection (per FR-19 + CR-01):
1. settings.ai_provider names a provider explicitly (mock/gemini/openai/anthropic) → honored as-is.
2. "auto" (the default) → the first provider with a key, in order: gemini, openai, anthropic.
3. No keys at all → mock (deterministic canned replies, for the sandbox).

A real API provider without a usable key fails at call time and falls back to mock (below).

Real providers are called over plain HTTPS with stdlib urllib — no new dependencies.
If a real provider fails after a retry — including replying with unparseable or
truncated JSON — the adapter logs a warning and falls back to the mock so the
store's customer still gets a safe answer (raw model output is NEVER shipped as
a customer-facing reply).
"""
from __future__ import annotations

import contextlib
import json
import logging
import os
import re
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from backend.core.config import get_settings
from backend.services.ai import prompts
from backend.shared.constants import (
    AI_ANTHROPIC_MODEL,
    AI_GEMINI_MODEL,
    AI_MAX_RETRIES,
    AI_MAX_OUTPUT_TOKENS,
    AI_MIN_CALL_INTERVAL_SECONDS,
    AI_OPENAI_MODEL,
    AI_RETRY_BACKOFF_FACTOR,
    AI_RETRY_MAX_SLEEP_SECONDS,
    AI_RETRY_SLEEP_SECONDS,
    AI_TIMEOUT_SECONDS,
    AI_PROVIDER_ANTHROPIC,
    AI_PROVIDER_GEMINI,
    AI_PROVIDER_MOCK,
    AI_PROVIDER_OPENAI,
    RAG_TOP_K,
)

logger = logging.getLogger("shop-assistant.ai")

# Client-side pacing state for real-provider requests (free-tier per-minute quotas).
_pace_lock = threading.Lock()
_last_real_request_at = 0.0  # time.monotonic() of the last real-provider HTTP request


class AiOutputError(ValueError):
    """The provider replied, but broke the strict-JSON output contract (non-JSON or truncated).

    Raised instead of shipping raw model text to the customer: the retry loop in
    _call_real_provider retries the call, and after the last attempt generate()
    falls back to the mock reply.
    """


# ============== RESPONSE MODEL ==============

@dataclass
class AiResponse:
    reply_text: str
    sentiment: str = "neutral"
    is_complaint: bool = False
    is_violation: bool = False
    violation_type: Optional[str] = None
    severity: Optional[str] = None
    product_id: Optional[str] = None
    transfer_request: bool = False
    prompt_tokens: int = 0
    completion_tokens: int = 0
    provider: str = AI_PROVIDER_MOCK
    raw: Optional[str] = field(default=None, repr=False)


# ============== PUBLIC ENTRY POINT ==============

def get_adapter() -> "AiAdapter":
    """Module-level singleton so provider selection runs once per process."""
    global _ADAPTER
    if _ADAPTER is None:
        _ADAPTER = AiAdapter()
    return _ADAPTER

_ADAPTER: Optional["AiAdapter"] = None


class AiAdapter:
    """Facade over the AI providers. One method: generate()."""

    def select_provider(self) -> str:
        settings = get_settings()
        explicit = settings.ai_provider.strip().lower()
        known = {AI_PROVIDER_MOCK, AI_PROVIDER_GEMINI, AI_PROVIDER_OPENAI, AI_PROVIDER_ANTHROPIC}
        if explicit in known:  # an explicit choice (including "mock") always wins
            return explicit
        keys = {
            AI_PROVIDER_GEMINI: settings.gemini_api_key,
            AI_PROVIDER_OPENAI: settings.openai_api_key,
            AI_PROVIDER_ANTHROPIC: settings.anthropic_api_key,
        }
        for provider, key in keys.items():  # dict order = gemini → openai → anthropic
            if key:
                return provider
        return AI_PROVIDER_MOCK

    def generate(
        self,
        *,
        persona_code: str,
        history: list[dict],
        context_items: list[dict],
        message: str,
        request_human: bool = False,
    ) -> AiResponse:
        """Generates one reply. `context_items` are the RAG top-K rows ({item_id, content})."""
        provider = self.select_provider()
        logger.info("AI provider: %s", provider)  # visible verification signal in service-api.log
        persona_instruction = prompts.PERSONA_INSTRUCTIONS.get(
            persona_code, prompts.PERSONA_INSTRUCTIONS[prompts.DEFAULT_PERSONA_CODE]
        )
        if provider == AI_PROVIDER_MOCK:
            return self._generate_mock(persona_instruction, history, context_items, message, request_human)

        system_prompt = prompts.CHAT_SYSTEM_PROMPT.format(persona_instruction=persona_instruction)
        user_prompt = prompts.CHAT_USER_PROMPT.format(
            context_count=len(context_items[:RAG_TOP_K]),
            context_block=prompts.build_context_block(context_items[:RAG_TOP_K]),
            history_block=prompts.build_history_block(history),
            message=message,
        )
        try:
            return self._call_real_provider(provider, system_prompt, user_prompt)
        except Exception as exc:  # noqa: BLE001 — any provider failure falls back to mock
            logger.warning("AI provider %s failed (%s); falling back to mock", provider, exc)
            return self._generate_mock(persona_instruction, history, context_items, message, request_human)

    # ============== MOCK PROVIDER (FR-19: fixed replies for the sandbox) ==============

    def _generate_mock(
        self,
        persona_instruction: str,
        history: list[dict],
        context_items: list[dict],
        message: str,
        request_human: bool,
    ) -> AiResponse:
        lowered = message.lower()

        if any(marker in lowered for marker in prompts.MOCK_ABUSE_MARKERS):
            return self._mock_response(
                prompts.MOCK_REPLY_VIOLATION,
                sentiment="negative", is_violation=True,
                violation_type="abuse", severity="high",
                prompt_text=message,
            )
        if request_human:
            return self._mock_response(
                prompts.MOCK_REPLY_TRANSFER,
                sentiment="neutral", transfer_request=True,
                prompt_text=message,
            )

        top_items = context_items[:RAG_TOP_K]
        if top_items:
            top = top_items[0]
            is_complaint = any(marker in lowered for marker in prompts.MOCK_COMPLAINT_MARKERS)
            reply = prompts.MOCK_REPLY_WITH_CONTEXT.format(
                item_count=len(top_items),
                item_ids=", ".join(str(item["item_id"]) for item in top_items),
                top_content=str(top["content"])[:200],
            )
            return self._mock_response(
                reply,
                sentiment="negative" if is_complaint else "positive",
                is_complaint=is_complaint,
                product_id=str(top["item_id"]) if top["item_id"] else None,
                prompt_text=message,
            )

        return self._mock_response(prompts.MOCK_REPLY_NO_DATA, sentiment="neutral", prompt_text=message)

    def _mock_response(
        self,
        reply: str,
        *,
        sentiment: str,
        prompt_text: str,
        is_complaint: bool = False,
        is_violation: bool = False,
        violation_type: Optional[str] = None,
        severity: Optional[str] = None,
        product_id: Optional[str] = None,
        transfer_request: bool = False,
    ) -> AiResponse:
        # Approximate token accounting (~4 chars per token) keeps TOKEN_USAGE meaningful in the sandbox.
        return AiResponse(
            reply_text=reply,
            sentiment=sentiment,
            is_complaint=is_complaint,
            is_violation=is_violation,
            violation_type=violation_type,
            severity=severity,
            product_id=product_id,
            transfer_request=transfer_request,
            prompt_tokens=max(1, len(prompt_text) // 4),
            completion_tokens=max(1, len(reply) // 4),
            provider=AI_PROVIDER_MOCK,
        )

    # ============== REAL PROVIDERS (stdlib HTTP, timeout + bounded retries) ==============

    def _call_real_provider(self, provider: str, system_prompt: str, user_prompt: str) -> AiResponse:
        settings = get_settings()
        last_error: Exception | None = None
        self._requested_retry_delay: float | None = None  # wait the provider asked for on a 429
        for attempt in range(AI_MAX_RETRIES + 1):
            if attempt:  # backoff between attempts: per-minute quota windows reset with time
                time.sleep(self._retry_delay(last_error, attempt))
            self._pace_real_request()
            try:
                if provider == AI_PROVIDER_GEMINI:
                    return self._call_gemini(settings.gemini_api_key, system_prompt, user_prompt)
                if provider == AI_PROVIDER_OPENAI:
                    return self._call_openai(settings.openai_api_key, system_prompt, user_prompt)
                if provider == AI_PROVIDER_ANTHROPIC:
                    return self._call_anthropic(settings.anthropic_api_key, system_prompt, user_prompt)
                raise ValueError(f"Unknown AI provider: {provider}")
            except Exception as exc:  # noqa: BLE001 — retried below, then handled by generate()
                last_error = exc
                if isinstance(exc, urllib.error.HTTPError):
                    # Drain the error body here: it releases the socket AND yields the
                    # provider's requested retry wait, honored by the next _retry_delay.
                    self._requested_retry_delay = self._drain_http_error(exc)
        raise RuntimeError(f"AI provider {provider} failed after retries: {last_error}") from last_error

    @staticmethod
    def _pace_real_request() -> None:
        """Spaces real-provider HTTP requests AI_MIN_CALL_INTERVAL_SECONDS apart.

        Free-tier Gemini keys allow ~10 requests/minute — bursty callers (the test suite)
        burn the whole per-minute window and every call comes back 429. Off by default
        (interval 0): paid / unthrottled keys pay no latency.
        """
        global _last_real_request_at
        if AI_MIN_CALL_INTERVAL_SECONDS <= 0:
            return
        with _pace_lock:
            wait = AI_MIN_CALL_INTERVAL_SECONDS - (time.monotonic() - _last_real_request_at)
            if wait > 0:
                time.sleep(wait)
            _last_real_request_at = time.monotonic()

    @staticmethod
    def _drain_http_error(exc: urllib.error.HTTPError) -> float | None:
        """Reads and closes an HTTP error body (socket hygiene) and extracts a retry hint.

        Google quota errors (429) carry the wait in the JSON body — google.rpc.RetryInfo's
        retryDelay ("25.056105s") or the message's "Please retry in 25.056105s" — while
        generic providers use the Retry-After header. Returns seconds, or None when absent.
        """
        raw_body = b""
        with contextlib.suppress(Exception):
            raw_body = exc.read()
        with contextlib.suppress(Exception):
            exc.close()
        with contextlib.suppress(Exception):
            header = (exc.headers or {}).get("Retry-After", "").strip()
            if header:
                return max(0.0, float(header))
        with contextlib.suppress(Exception):
            error = (json.loads(raw_body.decode("utf-8")) or {}).get("error") or {}
            for detail in error.get("details") or []:
                if "RetryInfo" in str(detail.get("@type", "")):
                    raw = str(detail.get("retryDelay", "")).strip().removesuffix("s")
                    if raw:
                        return max(0.0, float(raw))
            match = re.search(r"retry in (\d+(?:\.\d+)?)s", str(error.get("message", "")), re.IGNORECASE)
            if match:
                return float(match.group(1))
        return None

    def _retry_delay(self, last_error: Exception | None, attempt: int = 0) -> float:
        """Seconds to wait before the next attempt.

        On 429 the provider's requested wait (Retry-After header or the JSON-body
        retryDelay, captured by _drain_http_error) is honored — historically Google asked
        ~25s and the old 2s fixed pause re-hit the quota instantly (CR-01 run
        2026-11-13). Without a requested wait: exponential backoff 2s -> 4s -> 8s ...
        All waits capped so a chat request cannot hang forever.
        """
        requested = self._requested_retry_delay or 0.0
        self._requested_retry_delay = None
        base = AI_RETRY_SLEEP_SECONDS * (AI_RETRY_BACKOFF_FACTOR ** max(0, attempt - 1))
        if requested or (isinstance(last_error, urllib.error.HTTPError) and last_error.code == 429):
            return min(max(base, requested), AI_RETRY_MAX_SLEEP_SECONDS)
        return min(base, AI_RETRY_MAX_SLEEP_SECONDS)

    def _post_json(self, url: str, headers: dict, body: dict) -> dict:
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=AI_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))

    def _call_gemini(self, api_key: str, system_prompt: str, user_prompt: str) -> AiResponse:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{AI_GEMINI_MODEL}:generateContent?key={api_key}"
        )
        payload = self._post_json(url, {}, {
            "contents": [{"parts": [{"text": system_prompt + "\n\n" + user_prompt}]}],
            # Thinking-style Flash models spend part of this budget on internal reasoning
            # before the JSON starts, so the cap must leave room for both.
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": AI_MAX_OUTPUT_TOKENS,
                # Native JSON mode: the API itself rejects/rewrites non-JSON output, so the
                # strict-JSON contract no longer depends on prompt compliance alone
                # (client concern, 2026-11-13). _parse_provider_json still validates.
                "response_mime_type": "application/json",
            },
        })
        candidate = (payload.get("candidates") or [{}])[0]
        if candidate.get("finishReason") == "MAX_TOKENS":
            logger.warning("AI gemini output hit the token cap (finishReason=MAX_TOKENS) — JSON may be truncated")
        text = candidate["content"]["parts"][0]["text"]
        usage = payload.get("usageMetadata", {})
        return self._parse_provider_json(
            text,
            provider=AI_PROVIDER_GEMINI,
            prompt_tokens=int(usage.get("promptTokenCount", 0)),
            completion_tokens=int(usage.get("candidatesTokenCount", 0)),
        )

    def _call_openai(self, api_key: str, system_prompt: str, user_prompt: str) -> AiResponse:
        payload = self._post_json(
            "https://api.openai.com/v1/chat/completions",
            {"Authorization": f"Bearer {api_key}"},
            {
                "model": AI_OPENAI_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.7,
                "max_tokens": 1024,
            },
        )
        text = payload["choices"][0]["message"]["content"]
        usage = payload.get("usage", {})
        return self._parse_provider_json(
            text,
            provider=AI_PROVIDER_OPENAI,
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
        )

    def _call_anthropic(self, api_key: str, system_prompt: str, user_prompt: str) -> AiResponse:
        payload = self._post_json(
            "https://api.anthropic.com/v1/messages",
            {"x-api-key": api_key, "anthropic-version": "2023-06-01"},
            {
                "model": AI_ANTHROPIC_MODEL,
                "max_tokens": 1024,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            },
        )
        text = payload["content"][0]["text"]
        usage = payload.get("usage", {})
        return self._parse_provider_json(
            text,
            provider=AI_PROVIDER_ANTHROPIC,
            prompt_tokens=int(usage.get("input_tokens", 0)),
            completion_tokens=int(usage.get("output_tokens", 0)),
        )

    # ============== STRICT-JSON PARSING ==============

    def _parse_provider_json(
        self,
        text: str,
        *,
        provider: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> AiResponse:
        raw = text.strip()
        parsed = self._extract_json(raw)
        if parsed is None:
            # NEVER ship the raw text as the reply: the customer would see broken JSON and
            # the analysis would stay at its defaults. Raise → _call_real_provider retries
            # → after the last attempt generate() falls back to the safe mock reply.
            raise AiOutputError(
                f"{provider} broke the JSON contract (truncated or non-JSON output): {raw[:120]!r}"
            )
        return AiResponse(
            reply_text=str(parsed.get("reply", "")).strip() or raw,
            sentiment=str(parsed.get("sentiment", "neutral")),
            is_complaint=bool(parsed.get("is_complaint", False)),
            is_violation=bool(parsed.get("is_violation", False)),
            violation_type=parsed.get("violation_type"),
            severity=parsed.get("severity"),
            product_id=parsed.get("product_id"),
            transfer_request=bool(parsed.get("transfer_request", False)),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            provider=provider,
            raw=raw,
        )

    def _extract_json(self, text: str) -> Optional[dict]:
        """Finds the first JSON object in the text (tolerates markdown fences)."""
        start = text.find("{")
        if start == -1:
            return None
        end = text.rfind("}")
        if end <= start:
            return None
        try:
            parsed = json.loads(text[start:end + 1])
        except ValueError:
            return None
        return parsed if isinstance(parsed, dict) else None
