"""Conversations service — dashboard list + detail for the store owner (F06, FR-12/FR-13).

Read-only views over the tenant DB. 404 when a conversation is missing or belongs to
another store (the tenant session already isolates by store, so a missing row in this
store's DB means "not ours").
"""
from __future__ import annotations

import logging

from backend.core.errors import NotFoundError
from backend.schemas.chat import ChatAnalysisResponse, HistoryMessageResponse
from backend.schemas.conversations import (
    ConversationDetailResponse,
    ConversationListItem,
    ConversationListResponse,
)
from database.queries import (
    analyses as analyses_q,
    conversations as conversations_q,
    customers as customers_q,
    messages as messages_q,
)
from backend.shared.store_access import tenant_session_for_store

logger = logging.getLogger("shop-assistant.conversations")


# ============== LIST ==============

def list_conversations(
    *,
    store_id: int,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
) -> ConversationListResponse:
    """Returns paginated conversations for the dashboard table."""
    with tenant_session_for_store(store_id) as tconn:
        rows, total = conversations_q.get_conversations_paginated(
            tconn, page=page, page_size=page_size, status=status,
        )
    return ConversationListResponse(
        items=[_row_to_item(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


# ============== DETAIL ==============

def get_conversation_detail(*, store_id: int, conversation_id: int) -> ConversationDetailResponse:
    """Returns one conversation with its messages and analyses (404 when not ours)."""
    with tenant_session_for_store(store_id) as tconn:
        conversation = conversations_q.get_conversation(tconn, conversation_id)
        if conversation is None:
            raise NotFoundError("Conversation not found.")
        customer = customers_q.get_customer_by_id(tconn, int(conversation["customer_id"]))
        if customer is None:
            raise NotFoundError("Conversation not found.")
        message_rows = messages_q.list_conversation_messages(tconn, conversation_id=conversation_id)
        analyses: dict[int, object] = analyses_q.get_analyses_by_message_ids(
            tconn, [int(row["id"]) for row in message_rows],
        )

    item = ConversationListItem(
        id=int(conversation["id"]),
        status=str(conversation["status"]),
        customer_external_id=str(customer["external_id"]),
        case_status=str(customer["case_status"]),
        messages_count=len(message_rows),
        last_message_preview=str(message_rows[-1]["content"])[:200] if message_rows else None,
        started_at=str(conversation["started_at"]),
        last_message_at=str(conversation["last_message_at"]) if conversation["last_message_at"] else None,
    )
    messages = [
        HistoryMessageResponse(
            id=int(row["id"]),
            role=str(row["role"]),
            content=str(row["content"]),
            sent_at=str(row["sent_at"]),
            analysis=_analysis_response(analyses.get(int(row["id"]))),
        )
        for row in message_rows
    ]
    return ConversationDetailResponse(conversation=item, messages=messages)


# ============== INTERNAL HELPERS ==============

def _row_to_item(row) -> ConversationListItem:
    return ConversationListItem(
        id=int(row["id"]),
        status=str(row["status"]),
        customer_external_id=str(row["customer_external_id"]),
        case_status=str(row["case_status"]),
        messages_count=int(row["messages_count"]),
        last_message_preview=str(row["last_message_preview"])[:200] if row["last_message_preview"] else None,
        started_at=str(row["started_at"]),
        last_message_at=str(row["last_message_at"]) if row["last_message_at"] else None,
    )


def _analysis_response(analysis_row) -> ChatAnalysisResponse | None:
    if analysis_row is None:
        return None
    return ChatAnalysisResponse(
        sentiment=str(analysis_row["sentiment"] or "neutral"),
        is_complaint=bool(analysis_row["is_complaint"]),
        is_violation=bool(analysis_row["is_violation"]),
        violation_type=analysis_row["violation_type"],
        severity=analysis_row["severity"],
    )
