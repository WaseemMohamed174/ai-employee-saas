"""Conversations dashboard routes — store-owner views over chat history (F06, contract 8.4).

Dashboard API (JWT auth):
- GET /api/v1/dashboard/conversations        (?page&page_size&status)
- GET /api/v1/dashboard/conversations/{id}   → {conversation, messages(+analyses)}
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.core.deps import _resolve_store_id, get_current_user
from backend.core.errors import ApiResponse
from backend.services import conversations_service

router = APIRouter(prefix="/api/v1", tags=["conversations"])


# ============== DASHBOARD API: LIST CONVERSATIONS (JWT auth) ==============

@router.get("/dashboard/conversations")
def list_conversations_dashboard(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """List the store's conversations (paginated, optional status filter). Auth: Bearer JWT."""
    store_id = _resolve_store_id(current_user)
    result = conversations_service.list_conversations(
        store_id=store_id, page=page, page_size=page_size, status=status,
    )
    return ApiResponse.ok(result.model_dump())


# ============== DASHBOARD API: CONVERSATION DETAIL (JWT auth) ==============

@router.get("/dashboard/conversations/{conversation_id}")
def get_conversation_detail_dashboard(
    conversation_id: int,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """One conversation with its messages and analyses. 404 when missing or not ours."""
    store_id = _resolve_store_id(current_user)
    result = conversations_service.get_conversation_detail(
        store_id=store_id, conversation_id=conversation_id,
    )
    return ApiResponse.ok(result.model_dump())
