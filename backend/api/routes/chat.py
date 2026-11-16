"""Chat routes — the public API for store widgets (contract 8.3).

- POST /api/v1/chat                        (X-API-Key header) — the core entry point
- GET  /api/v1/conversations/{id}/history  (X-API-Key header) — conversation memory

Per CODE_RULES 6.2: routes receive the request and return the response —
the whole flow lives in chat_service.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.core.deps import get_current_api_key
from backend.core.errors import ApiResponse
from backend.schemas.chat import ChatRequest
from backend.services import chat_service, rate_limit_service

router = APIRouter(prefix="/api/v1", tags=["chat"])


# ============== PUBLIC API: CHAT (API key auth) ==============

@router.post("/chat")
def send_chat_message(
    payload: ChatRequest,
    auth: dict = Depends(get_current_api_key),
) -> dict:
    """Receives one store-customer message and returns the unified AI response (FR-11).

    Body: {conversation_id?, customer_external_id, message, request_human?}
    """
    key = auth["api_key"]
    rate_limit_service.check_rate_limit(int(key["id"]))
    result = chat_service.handle_message(store=auth["store"], payload=payload)
    return ApiResponse.ok(result.model_dump())


# ============== PUBLIC API: CONVERSATION HISTORY (API key auth) ==============

@router.get("/conversations/{conversation_id}/history")
def get_conversation_history(
    conversation_id: int,
    auth: dict = Depends(get_current_api_key),
) -> dict:
    """Returns the full message list of one conversation (FR-09 memory, contract 8.3)."""
    result = chat_service.get_history(store=auth["store"], conversation_id=conversation_id)
    return ApiResponse.ok(result.model_dump())
