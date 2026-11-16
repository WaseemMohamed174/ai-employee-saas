"""Subscription routes — Plans & Usage dashboard (F14) + the contract 8.2 switch endpoint.

Dashboard API (owner only):
- GET  /api/v1/dashboard/plans   (JWT — current subscription + paid catalog + usage)
- POST /api/v1/subscriptions     (JWT — {plan_code, stripe_token?} → {subscription, checkout_url, mode})
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.core.deps import get_current_user
from backend.core.errors import ApiResponse
from backend.schemas.subscription import SubscriptionChangeRequest
from backend.services import subscription_service

router = APIRouter(prefix="/api/v1", tags=["subscriptions"])


# ============== PLANS & USAGE OVERVIEW ==============

@router.get("/dashboard/plans")
def get_plans_overview(current_user: dict = Depends(get_current_user)) -> dict:
    """Returns the owner's current subscription, the paid catalog and the usage stats (FR-03, FR-13)."""
    result = subscription_service.get_plans_overview(int(current_user["id"]))
    return ApiResponse.ok(result.model_dump())


# ============== CHANGE SUBSCRIPTION (mock checkout) ==============

@router.post("/subscriptions")
def change_subscription(
    payload: SubscriptionChangeRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Switches the store's plan (contract 8.2). Mock checkout: immediate activation.

    403 no store yet; 422 unknown plan / free_trial target / already on the plan.
    """
    result = subscription_service.change_subscription(
        int(current_user["id"]),
        payload.plan_code,
        payload.stripe_token,
    )
    return ApiResponse.ok(result.model_dump())
