"""Violations dashboard routes — the store-owner violations table + policies (F08, contract 8.4).

Dashboard API (JWT auth):
- GET  /api/v1/dashboard/violations          (?page&page_size&action)
- GET  /api/v1/dashboard/violations/policies
- POST /api/v1/dashboard/violations/policy
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.core.deps import _resolve_store_id, get_current_user
from backend.core.errors import ApiResponse
from backend.schemas.violations import ViolationPolicyCreate
from backend.services import violations_service

router = APIRouter(prefix="/api/v1", tags=["violations"])


# ============== DASHBOARD API: LIST VIOLATIONS (JWT auth) ==============

@router.get("/dashboard/violations")
def list_violations_dashboard(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    action: str | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """List the store's recorded violations (paginated, optional action filter)."""
    store_id = _resolve_store_id(current_user)
    result = violations_service.list_violations(
        store_id=store_id, page=page, page_size=page_size, action=action,
    )
    return ApiResponse.ok(result.model_dump())


# ============== DASHBOARD API: POLICIES (FR-14) ==============

@router.get("/dashboard/violations/policies")
def list_violation_policies(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """List the store's escalation policies in escalation order."""
    store_id = _resolve_store_id(current_user)
    result = violations_service.list_policies(store_id=store_id)
    return ApiResponse.ok(result.model_dump())


@router.post("/dashboard/violations/policy")
def save_violation_policy(
    payload: ViolationPolicyCreate,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Create or update one escalation policy (same action = upsert, FR-14)."""
    store_id = _resolve_store_id(current_user)
    result = violations_service.save_policy(store_id=store_id, payload=payload)
    return ApiResponse.ok(result.model_dump())
