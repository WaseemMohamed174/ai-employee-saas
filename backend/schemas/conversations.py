"""Conversations dashboard schemas — list + detail responses (F06, contract 8.4)."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from backend.schemas.chat import HistoryMessageResponse


# ============== RESPONSE SCHEMAS ==============

class ConversationListItem(BaseModel):
    """One row in the dashboard conversations table."""
    id: int
    status: str
    customer_external_id: str
    case_status: str
    messages_count: int
    last_message_preview: Optional[str] = None
    started_at: str
    last_message_at: Optional[str] = None


class ConversationListResponse(BaseModel):
    items: list[ConversationListItem]
    total: int
    page: int
    page_size: int


class ConversationDetailResponse(BaseModel):
    """The detail view: the conversation header + its messages with analyses."""
    conversation: ConversationListItem
    messages: list[HistoryMessageResponse]
