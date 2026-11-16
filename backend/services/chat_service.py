"""Chat service — the core flow of one customer message (WORKFLOW 4.1, FR-07..FR-11).

Order per the sequence diagram:
1. resolve customer + banned check (banned → ignored, nothing saved, quota untouched)
2. plan conversation limit (new conversations only, matching usage.conversations_used)
3. save the user message + read history
4. RAG top-5 keyword search
5. AI adapter call (no DB session held during the provider call)
6. save assistant message + analysis + token usage; apply violation / transfer / alerts
7. return the one unified response (FR-11)
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from backend.core.errors import ForbiddenError, NotFoundError, ValidationError
from backend.schemas.chat import (
    ChatAnalysisResponse,
    ChatRequest,
    ChatResponse,
    HistoryMessageResponse,
    HistoryResponse,
    TransferRequestResponse,
)
from backend.services.ai import get_adapter
from backend.services import persona_service
from backend.services import rag_service
from database.connection import platform_session, tenant_session
from database.queries import (
    alerts as alerts_q,
    analyses as analyses_q,
    conversations as conversations_q,
    customers as customers_q,
    messages as messages_q,
    subscriptions as subs_q,
    token_usage as token_usage_q,
    transfer_requests as transfer_q,
    violations as violations_q,
)
from backend.shared.constants import (
    ALERT_NEW_VIOLATION,
    ALERT_TOKEN_NEAR_LIMIT,
    ALERT_TRANSFER_PENDING,
    CASE_BANNED,
    CASE_TRANSFERRED,
    CASE_WARNED,
    CHAT_HISTORY_LIMIT,
    CHAT_ROLE_ASSISTANT,
    CHAT_ROLE_USER,
    CONVERSATION_STATUS_TRANSFERRED,
    DEFAULT_VIOLATION_ACTION,
    HIGH_SEVERITY_VIOLATION_ACTION,
    POLICY_BASELINE_ACTION,
    TOKEN_NEAR_LIMIT_PERCENT,
    TRANSFER_STATUS_PENDING,
    VIOLATION_PERMA_BAN,
    VIOLATION_SEVERITY_HIGH,
    VIOLATION_TEMP_BAN,
)

logger = logging.getLogger("shop-assistant.chat")

TEMP_BAN_HOURS = 24


# ============== PUBLIC API ==============

def handle_message(*, store: dict, payload: ChatRequest) -> ChatResponse:
    """Processes one customer message and returns the unified response (FR-11)."""
    slug = str(store["slug"])
    conversation_limit = _conversation_limit(store)

    # ============== 1. CUSTOMER + BANNED CHECK (FR-15) ==============
    with tenant_session(slug) as conn:
        customer = customers_q.get_or_create_customer(conn, external_id=payload.customer_external_id)
        customer_id = int(customer["id"])
        case_status = str(customer["case_status"])
    if case_status == CASE_BANNED:
        return ChatResponse(case_status=CASE_BANNED)

    # ============== 2. CONVERSATION + PLAN LIMIT + USER MESSAGE ==============
    with tenant_session(slug) as conn:
        conversation_id = _resolve_conversation(conn, customer_id, payload, conversation_limit)
        messages_q.create_message(
            conn, conversation_id=conversation_id, role=CHAT_ROLE_USER, content=payload.message,
        )
        recent = messages_q.get_conversation_messages(
            conn, conversation_id=conversation_id, limit=CHAT_HISTORY_LIMIT + 1,
        )
        history = [{"role": str(row["role"]), "content": str(row["content"])} for row in recent[:-1]]

    # ============== 3. RAG TOP 5 (FR-07) ==============
    with tenant_session(slug) as conn:
        context_items = rag_service.search_top5(conn, payload.message)
    top_row_id = context_items[0]["row_id"] if context_items else None
    logger.info("RAG context items: %d", len(context_items))  # observable signal for tests (CR-01)

    # ============== 4. AI PROVIDER (FR-08) — no DB session held ==============
    # FR-16: the store's dashboard persona choice steers the reply tone; stores that
    # never picked one keep the platform default (professional).
    persona_code = persona_service.resolve_persona_code_for_store(store)
    ai_resp = get_adapter().generate(
        persona_code=persona_code,
        history=history,
        context_items=context_items,
        message=payload.message,
        request_human=payload.request_human,
    )

    # ============== 5. PERSIST EVERYTHING + SIDE EFFECTS ==============
    transfer_info: TransferRequestResponse | None = None
    with tenant_session(slug) as conn:
        assistant_id = messages_q.create_message(
            conn, conversation_id=conversation_id, role=CHAT_ROLE_ASSISTANT,
            content=ai_resp.reply_text, store_data_id=top_row_id, ai_decision_raw=ai_resp.raw,
        )
        analyses_q.create_analysis(
            conn, message_id=assistant_id, sentiment=ai_resp.sentiment,
            is_complaint=ai_resp.is_complaint, is_violation=ai_resp.is_violation,
            violation_type=ai_resp.violation_type, severity=ai_resp.severity,
        )
        token_usage_q.record_usage(
            conn, message_id=assistant_id,
            prompt_tokens=ai_resp.prompt_tokens, completion_tokens=ai_resp.completion_tokens,
        )
        conversations_q.touch_last_message(conn, conversation_id)

        if ai_resp.is_violation:
            case_status = _apply_violation(conn, customer_id, ai_resp.violation_type, ai_resp.severity)
        if payload.request_human or ai_resp.transfer_request:
            transfer_info = _create_transfer(conn, customer_id, conversation_id, ai_resp.reply_text)
            case_status = CASE_TRANSFERRED
        _maybe_alert_token_near_limit(conn, store)

    return ChatResponse(
        reply=ai_resp.reply_text,
        analysis=ChatAnalysisResponse(
            sentiment=ai_resp.sentiment,
            is_complaint=ai_resp.is_complaint,
            is_violation=ai_resp.is_violation,
            violation_type=ai_resp.violation_type,
            severity=ai_resp.severity,
        ),
        product_id=ai_resp.product_id,
        case_status=case_status,
        transfer_request=transfer_info,
        conversation_id=conversation_id,
        message_id=assistant_id,
    )


def get_history(*, store: dict, conversation_id: int) -> HistoryResponse:
    """Returns a conversation's messages with analyses (contract 8.3: 403 when not ours)."""
    slug = str(store["slug"])
    with tenant_session(slug) as conn:
        conversation = conversations_q.get_conversation(conn, conversation_id)
        if conversation is None:
            raise ForbiddenError("Conversation not found in this store.")
        rows = messages_q.get_conversation_messages(conn, conversation_id=conversation_id)
        analyses: dict[int, object] = analyses_q.get_analyses_by_message_ids(
            conn, [int(row["id"]) for row in rows],
        )
    messages = []
    for row in rows:
        analysis_row = analyses.get(int(row["id"]))
        messages.append(HistoryMessageResponse(
            id=int(row["id"]),
            role=str(row["role"]),
            content=str(row["content"]),
            sent_at=str(row["sent_at"]),
            analysis=ChatAnalysisResponse(
                sentiment=str(analysis_row["sentiment"] or "neutral"),
                is_complaint=bool(analysis_row["is_complaint"]),
                is_violation=bool(analysis_row["is_violation"]),
                violation_type=analysis_row["violation_type"],
                severity=analysis_row["severity"],
            ) if analysis_row else None,
        ))
    return HistoryResponse(conversation_id=conversation_id, messages=messages)


# ============== INTERNAL HELPERS ==============

def _conversation_limit(store: dict) -> int:
    """The active plan's conversation_limit_month (0 when no subscription → chat refused)."""
    with platform_session() as conn:
        sub = subs_q.get_active_subscription(conn, int(store["id"]))
    if sub is None:
        raise NotFoundError("No active subscription found for this store.")
    return int(sub["conversation_limit_month"])


def _resolve_conversation(conn, customer_id: int, payload: ChatRequest, conversation_limit: int) -> int:
    """Returns the conversation id: the given one (validated) or a new one (plan-checked)."""
    if payload.conversation_id is not None:
        conversation = conversations_q.get_conversation(conn, payload.conversation_id)
        if conversation is None or int(conversation["customer_id"]) != customer_id:
            raise ValidationError("Unknown conversation_id for this customer.")
        return payload.conversation_id
    started_this_month = conversations_q.count_started_this_month(conn)
    if started_this_month >= conversation_limit:
        raise ForbiddenError(
            f"Monthly conversation limit reached ({started_this_month}/{conversation_limit}). "
            f"Upgrade your plan to keep chatting."
        )
    return conversations_q.create_conversation(conn, customer_id=customer_id)


def _apply_violation(conn, customer_id: int, violation_type: str | None, severity: str | None) -> str:
    """Records the violation and applies the resulting action (F08 policy ladder).

    With auto-apply policies: the current violation is the (count + 1)-th inside each
    policy's window; the most severe satisfied policy wins; below all thresholds the
    ladder starts at the baseline (warning). Without any auto-apply policy the store
    keeps the built-in defaults (high severity → perma_ban, else warning).
    """
    action = _resolve_policy_action(conn, customer_id=customer_id, severity=severity)
    expires_at = None
    if action == VIOLATION_TEMP_BAN:
        expires_at = (datetime.utcnow() + timedelta(hours=TEMP_BAN_HOURS)).strftime("%Y-%m-%d %H:%M:%S")
    violations_q.create_violation(
        conn, customer_id=customer_id, action=action,
        reason=violation_type or "policy_violation", expires_at=expires_at,
    )
    if not alerts_q.has_active_alert_of_type(conn, ALERT_NEW_VIOLATION):
        alerts_q.create_alert(
            conn, type=ALERT_NEW_VIOLATION, severity="warning",
            message=f"New violation ({action}) recorded for customer #{customer_id}.",
        )
    if action == VIOLATION_TEMP_BAN or action == VIOLATION_PERMA_BAN:
        customers_q.set_case_status(conn, customer_id=customer_id, status=CASE_BANNED, banned_reason=violation_type)
        return CASE_BANNED
    customers_q.set_case_status(conn, customer_id=customer_id, status=CASE_WARNED)
    return CASE_WARNED


def _resolve_policy_action(conn, *, customer_id: int, severity: str | None) -> str:
    """The action for the violation being recorded: the auto-apply ladder, or the defaults."""
    policies = violations_q.get_auto_apply_policies(conn)
    if not policies:
        return (
            HIGH_SEVERITY_VIOLATION_ACTION
            if severity == VIOLATION_SEVERITY_HIGH else DEFAULT_VIOLATION_ACTION
        )
    action = POLICY_BASELINE_ACTION
    for policy in policies:  # escalation order — the last satisfied policy wins
        count = violations_q.count_violations_in_window(
            conn, customer_id=customer_id, window_hours=int(policy["threshold_window_hours"]),
        )
        if count + 1 >= int(policy["threshold_count"]):
            action = str(policy["action"])
    return action


def _create_transfer(conn, customer_id: int, conversation_id: int, reply_text: str) -> TransferRequestResponse:
    """Creates the transfer request + pending alert and marks the customer transferred (FR-10).

    Also marks the conversation itself as 'transferred' so the F06 dashboard status
    filter has real data to filter on.
    """
    transfer_id = transfer_q.create_transfer_request(
        conn, conversation_id=conversation_id, customer_id=customer_id, reason=reply_text[:200],
    )
    conversations_q.set_status(conn, conversation_id, CONVERSATION_STATUS_TRANSFERRED)
    if not alerts_q.has_active_alert_of_type(conn, ALERT_TRANSFER_PENDING):
        alerts_q.create_alert(
            conn, type=ALERT_TRANSFER_PENDING, severity="info",
            message=f"Customer #{customer_id} asked for a human agent.",
        )
    return TransferRequestResponse(id=transfer_id, status=TRANSFER_STATUS_PENDING)


def _maybe_alert_token_near_limit(conn, store: dict) -> None:
    """Raises token_near_limit once when monthly usage crosses 90% of the plan limit."""
    with platform_session() as conn_platform:
        sub = subs_q.get_active_subscription(conn_platform, int(store["id"]))
    if sub is None or int(sub["token_limit_month"]) <= 0:
        return
    month_tokens = token_usage_q.get_month_tokens(conn)
    limit = int(sub["token_limit_month"])
    if month_tokens >= limit * TOKEN_NEAR_LIMIT_PERCENT // 100 and not alerts_q.has_active_alert_of_type(conn, ALERT_TOKEN_NEAR_LIMIT):
        alerts_q.create_alert(
            conn, type=ALERT_TOKEN_NEAR_LIMIT, severity="warning",
            message=f"Token usage at {month_tokens}/{limit} (over {TOKEN_NEAR_LIMIT_PERCENT}% of your plan).",
        )
