"""Overview dashboard routes — the owner's stats + charts + activity page (F15, contract 8.4).

Dashboard API (JWT auth):
- GET /api/v1/dashboard/overview → {stats, uploads_per_day, items_by_source,
  keys_by_status, recent_uploads, recent_conversations, recent_alerts}
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.core.deps import _resolve_store_id, get_current_user
from backend.core.errors import ApiResponse
from backend.services import overview_service

router = APIRouter(prefix="/api/v1", tags=["overview"])


# ============== DASHBOARD API: OVERVIEW PAGE (JWT auth) ==============

@router.get("/dashboard/overview")
def get_overview_dashboard(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Stats + charts + recent activity for this store, in one read-only response.

    Fresh stores answer honest zeros for the AI-driven counters; the uploads
    series is always exactly 14 ascending UTC days. See overview_service.
    """
    store_id = _resolve_store_id(current_user)
    result = overview_service.get_overview(store_id=store_id)
    return ApiResponse.ok(result.model_dump())
