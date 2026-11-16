"""Store routes — create store, get current user's store, get usage.

All routes require authentication (get_current_user dependency).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.core.deps import get_current_user
from backend.core.errors import ApiResponse
from backend.schemas.store import StoreCreateRequest
from backend.services import store_service

router = APIRouter(prefix="/api/v1", tags=["stores"])


# ============== CREATE STORE ==============

@router.post("/stores")
def create_store(payload: StoreCreateRequest, current_user: dict = Depends(get_current_user)) -> dict:
    """Create a new store for the current user. Auto-creates a Free Trial subscription."""
    result = store_service.create_store(
        owner_user_id=int(current_user["id"]),
        slug=payload.slug,
        name=payload.name,
    )
    return ApiResponse.ok(result.model_dump())


# ============== GET MY STORE ==============

@router.get("/stores/me")
def get_my_store(current_user: dict = Depends(get_current_user)) -> dict:
    """Returns the current user's store + subscription + usage; `data: null` when no store yet.

    The dashboard probes this endpoint on every visit and a fresh account has no
    store — a 404 there used to paint the browser console red on every page load
    (the frontend handles the empty state fine). 200 + `data: null` keeps the
    same information while keeping the console clean. /usage keeps its strict 404.
    """
    result = store_service.get_my_store_optional(int(current_user["id"]))
    if result is None:
        return ApiResponse.ok(None)
    return ApiResponse.ok(result.model_dump())


# ============== GET USAGE ==============

@router.get("/usage")
def get_usage(current_user: dict = Depends(get_current_user)) -> dict:
    """Returns usage stats for the current user's store."""
    result = store_service.get_my_store(int(current_user["id"]))
    return ApiResponse.ok(result.usage.model_dump())
