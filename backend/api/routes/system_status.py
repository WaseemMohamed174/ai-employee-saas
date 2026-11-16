"""System status dashboard routes — the owner's service health page (F12, contract 8.4).

Dashboard API (JWT auth):
- GET /api/v1/dashboard/system-status → {overall, operational_count, degraded_count,
  version, uptime_seconds, generated_at, services: [...]}
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.core.deps import _resolve_store_id, get_current_user
from backend.core.errors import ApiResponse
from backend.services import system_status_service

router = APIRouter(prefix="/api/v1", tags=["system-status"])


# ============== DASHBOARD API: SYSTEM STATUS PAGE (JWT auth) ==============

@router.get("/dashboard/system-status")
def get_system_status_dashboard(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """The whole platform health in one read-only response (no external calls).

    Every service row is derived from live process and configuration state; provider
    keys are never echoed. See system_status_service for the row rules.
    """
    store_id = _resolve_store_id(current_user)
    result = system_status_service.get_system_status(store_id=store_id)
    return ApiResponse.ok(result.model_dump())
