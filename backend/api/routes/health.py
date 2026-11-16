"""Health check route.

GET /api/health — returns `{ ok: true, data: { status, version, time } }`.
Used by the Launcher's health probe and by the demo store's status check.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from backend.core.errors import ApiResponse
from backend.shared.constants import APP_NAME, APP_VERSION

router = APIRouter()


@router.get("/api/health")
def health() -> dict:
    """Returns the service health. Always 200 if the app is running."""
    return ApiResponse.ok({
        "status": "healthy",
        "service": APP_NAME,
        "version": APP_VERSION,
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
