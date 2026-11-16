"""Chat schemas — Pydantic models for the public chat API (contract 8.3)."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from backend.shared.constants import CHAT_MESSAGE_MAX_CHARS


# ============== REQUEST SCHEMAS ==============

class ChatRequest(BaseModel):
    """Body for POST /api/v1/chat.

    `conversation_id` is optional: omit it to start a new conversation.
    `request_human` is the customer accepting the transfer offer (FR-10).
    """
    conversation_id: Optional[int] = None
    customer_external_id: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=CHAT_MESSAGE_MAX_CHARS)
    request_human: bool = False


# ============== RESPONSE SCHEMAS ==============

class ChatAnalysisResponse(BaseModel):
    sentiment: str
    is_complaint: bool
    is_violation: bool
    violation_type: Optional[str] = None
    severity: Optional[str] = None


class TransferRequestResponse(BaseModel):
    id: int
    status: str
    reason: Optional[str] = None


class ChatResponse(BaseModel):
    """The single unified response (FR-11). reply/analysis/message_id are null for banned customers."""
    reply: Optional[str] = None
    analysis: Optional[ChatAnalysisResponse] = None
    product_id: Optional[str] = None
    case_status: str
    transfer_request: Optional[TransferRequestResponse] = None
    conversation_id: Optional[int] = None
    message_id: Optional[int] = None


class HistoryMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    sent_at: str
    analysis: Optional[ChatAnalysisResponse] = None


class HistoryResponse(BaseModel):
    conversation_id: int
    customer_external_id: Optional[str] = None
    messages: list[HistoryMessageResponse]
