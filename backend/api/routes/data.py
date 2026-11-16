"""Data routes — public API (API key auth) + dashboard API (JWT auth).

Public API (for store widgets / integrations):
- POST /api/v1/data  (X-API-Key header)

Dashboard API (for the store owner):
- GET  /api/v1/dashboard/database        (JWT, paginated list)
- POST /api/v1/dashboard/database/upload (JWT, JSON body)
- GET  /api/v1/dashboard/database/logs   (JWT, upload logs)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.core.deps import _resolve_store_id, get_current_api_key, get_current_user
from backend.core.errors import ApiResponse
from backend.schemas.data import DataUploadRequest
from backend.services import data_service

router = APIRouter(prefix="/api/v1", tags=["data"])


# ============== PUBLIC API: UPLOAD DATA (API key auth) ==============

@router.post("/data")
def upload_data_api(
    payload: DataUploadRequest,
    auth: dict = Depends(get_current_api_key),
) -> dict:
    """Upload store data via the public API. Auth: X-API-Key header.

    Body: {items: [{id, content}], source: "api"}
    Each item's `id` is the store's own identifier (e.g. product SKU).
    """
    store = auth["store"]
    result = data_service.upload_data(
        store_id=int(store["id"]),
        items=[item.model_dump() for item in payload.items],
        source=payload.source,
    )
    return ApiResponse.ok(result.model_dump())


# ============== DASHBOARD API: LIST DATA (JWT auth) ==============

@router.get("/dashboard/database")
def list_data_dashboard(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """List store data items (paginated). Auth: Bearer JWT."""
    store_id = _resolve_store_id(current_user)
    result = data_service.list_data(store_id=store_id, page=page, page_size=page_size)
    return ApiResponse.ok(result.model_dump())


# ============== DASHBOARD API: UPLOAD DATA (JWT auth) ==============

@router.post("/dashboard/database/upload")
def upload_data_dashboard(
    payload: DataUploadRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Upload store data via the dashboard. Auth: Bearer JWT.

    Body: {items: [{id, content}], source: "dashboard"}
    """
    store_id = _resolve_store_id(current_user)
    result = data_service.upload_data(
        store_id=store_id,
        items=[item.model_dump() for item in payload.items],
        source="dashboard",
        uploaded_by_user_id=int(current_user["id"]),
    )
    return ApiResponse.ok(result.model_dump())


# ============== DASHBOARD API: UPLOAD LOGS (JWT auth) ==============

@router.get("/dashboard/database/logs")
def list_upload_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """List upload log entries (audit trail). Auth: Bearer JWT."""
    from backend.schemas.data import upload_log_to_response
    from database.connection import platform_session, tenant_session
    from database.queries import data_upload_log as log_q
    from database.queries import stores as stores_q

    store_id = _resolve_store_id(current_user)
    with platform_session() as conn:
        store = stores_q.get_store_by_id(conn, store_id)
    if store is None:
        return ApiResponse.ok({"logs": [], "total": 0, "page": page, "page_size": page_size})
    slug = str(store["slug"])
    with tenant_session(slug) as tconn:
        rows, total = log_q.get_logs_paginated(tconn, page=page, page_size=page_size)
    return ApiResponse.ok({
        "logs": [upload_log_to_response(row).model_dump() for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    })
