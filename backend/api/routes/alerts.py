"""Alerts dashboard routes — the store-owner alerts table + dismiss (F10, contract 8.4).

Dashboard API (JWT auth):
- GET  /api/v1/dashboard/alerts                     (?page&page_size&type&status; evaluates complaint_spike first)
- POST /api/v1/dashboard/alerts/{alert_id}/dismiss
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.core.deps import _resolve_store_id, get_current_user
from backend.core.errors import ApiResponse
from backend.services import alerts_service
from backend.shared import constants as C

router = APIRouter(prefix="/api/v1", tags=["alerts"])


# ============== DASHBOARD API: LIST ALERTS (JWT auth) ==============

@router.get("/dashboard/alerts")
def list_alerts_dashboard(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    type: str | None = Query(default=None),
    status: str = Query(default=C.ALERT_STATUS_ALL),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """List the store's alerts (paginated, optional type + status filters).

    Evaluates the dashboard-computed complaint_spike (PRD 4.5) before listing,
    so a fresh spike shows up in the very same response.
    """
    store_id = _resolve_store_id(current_user)
    result = alerts_service.list_alerts(
        store_id=store_id, page=page, page_size=page_size, type=type, status=status,
    )
    return ApiResponse.ok(result.model_dump())


# ============== DASHBOARD API: DISMISS (lifecycle 6.3) ==============

@router.post("/dashboard/alerts/{alert_id}/dismiss")
def dismiss_alert(
    alert_id: int,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Stamp dismissed_at on one alert (active → dismissed; 404 unknown; idempotent)."""
    store_id = _resolve_store_id(current_user)
    result = alerts_service.dismiss_alert(store_id=store_id, alert_id=alert_id)
    return ApiResponse.ok(result.model_dump())
