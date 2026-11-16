"""Complaints dashboard routes — the store-owner complaints table (F07, contract 8.4).

Dashboard API (JWT auth):
- GET /api/v1/dashboard/complaints   (?page&page_size&sentiment)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.core.deps import _resolve_store_id, get_current_user
from backend.core.errors import ApiResponse
from backend.services import complaints_service

router = APIRouter(prefix="/api/v1", tags=["complaints"])


# ============== DASHBOARD API: LIST COMPLAINTS (JWT auth) ==============

@router.get("/dashboard/complaints")
def list_complaints_dashboard(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sentiment: str | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """List the store's complaints (flagged messages, paginated, optional sentiment filter).

    Auth: Bearer JWT. Only analyses with is_complaint = 1 are returned.
    """
    store_id = _resolve_store_id(current_user)
    result = complaints_service.list_complaints(
        store_id=store_id, page=page, page_size=page_size, sentiment=sentiment,
    )
    return ApiResponse.ok(result.model_dump())
