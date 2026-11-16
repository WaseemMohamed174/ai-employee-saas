"""Plan routes — public catalog endpoints.

Per FR-02: any visitor (even unauthenticated) can see the plans and features.
"""
from __future__ import annotations

from fastapi import APIRouter

from backend.core.errors import ApiResponse
from backend.services import plan_service

router = APIRouter(prefix="/api/v1", tags=["plans"])


# ============== LIST PLANS ==============

@router.get("/plans")
def list_plans() -> dict:
    """Returns the plan catalog (free_trial, starter, pro, business). Public — no auth required."""
    plans = plan_service.list_plans()
    return ApiResponse.ok({"plans": [p.model_dump() for p in plans]})
