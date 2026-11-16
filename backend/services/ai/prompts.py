"""Prompt templates for the AI chat (FR-08/FR-09/FR-10).

Kept in their own file per CODE_RULES 6.2 — no prompt text buried in functions.
The real providers receive the full strict-JSON instruction; the mock provider
uses the same inputs to build deterministic canned replies for the sandbox.
"""
from __future__ import annotations

from backend.shared.constants import (
    PERSONA_CONCISE,
    PERSONA_DETAILED,
    PERSONA_FRIENDLY,
    PERSONA_PROFESSIONAL,
)

# ============== PERSONA INSTRUCTIONS (FR-16) ==============
# The DB catalog (seed_personas.py, F11) is the dashboard-facing source of truth;
# this dict keeps the identical instructions as the adapter's fallback for codes
# that never reached a catalog row (e.g. a store that never picked one).

PERSONA_INSTRUCTIONS: dict[str, str] = {
    PERSONA_FRIENDLY: "You are warm and casual. Use the customer's language and light emojis where natural.",
    PERSONA_PROFESSIONAL: "You are polished and formal. No emojis. Keep a helpful, professional tone.",
    PERSONA_CONCISE: "Answer in at most 2 short sentences unless the customer asks for detail.",
    PERSONA_DETAILED: "Give full explanations with context and concrete examples.",
}

DEFAULT_PERSONA_CODE = PERSONA_PROFESSIONAL

# ============== SYSTEM PROMPT ==============

CHAT_SYSTEM_PROMPT = """You are the AI employee of an e-commerce store, chatting with the store's customer.
Persona: {persona_instruction}
Answer the customer ONLY from the store data below. If the answer is not in the store data,
say politely that the information is not available and offer to transfer them to a human team member.
Reply in the same language the customer writes in (FR-09).

Respond with ONLY a valid JSON object, no markdown fences, using exactly these keys:
{{
  "reply": "<your answer to the customer>",
  "sentiment": "<positive | neutral | negative>",
  "is_complaint": <true when the customer is complaining about the store/service>,
  "is_violation": <true when the customer is abusive, threatening or harassing>,
  "violation_type": "<abuse | threat | spam> or null",
  "severity": "<low | medium | high> or null",
  "product_id": "<the store data item id that answers the question> or null",
  "transfer_request": <true only when the customer explicitly asks for a human or accepts the transfer offer>
}}"""

CHAT_USER_PROMPT = """Store data ({context_count} items, most relevant first):
{context_block}

Conversation history so far:
{history_block}

Customer's new message: {message}"""

# ============== MOCK REPLIES (deterministic canned replies for sandbox testing, per FR-19) ==============

MOCK_REPLY_WITH_CONTEXT = (
    "Based on {item_count} item(s) from our store data"
    " (top matches: {item_ids}): {top_content}"
)

MOCK_REPLY_NO_DATA = (
    "I'm sorry, I don't have that information in our store data right now."
    " Would you like me to transfer you to a human team member?"
)

MOCK_REPLY_TRANSFER = (
    "You're being transferred to a human team member."
    " They will follow up with you shortly — thank you for your patience."
)

MOCK_REPLY_VIOLATION = (
    "Your message violates our community guidelines."
    " This incident has been recorded and reported to the store owner."
)

# Words that make the mock provider treat the message as abusive (high severity violation).
MOCK_ABUSE_MARKERS = ("idiot", "stupid", "moron", "hate you all", "scammers")

# Words that make the mock provider flag a complaint.
MOCK_COMPLAINT_MARKERS = ("terrible", "awful", "worst", "never again", "complain about")


def build_context_block(context_items: list[dict]) -> str:
    """Formats the RAG paragraphs as a numbered block for the prompt."""
    lines = []
    for index, item in enumerate(context_items, start=1):
        lines.append(f"[{index}] (id={item['item_id']}) {item['content']}")
    return "\n".join(lines) if lines else "(no store data uploaded yet)"


def build_history_block(history: list[dict]) -> str:
    """Formats past conversation turns; history items are {role, content}."""
    if not history:
        return "(this is the first message)"
    lines = []
    for turn in history:
        who = "Customer" if turn["role"] == "user" else "You"
        lines.append(f"{who}: {turn['content']}")
    return "\n".join(lines)
