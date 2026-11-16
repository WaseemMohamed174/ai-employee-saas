"""Subscription schemas — Pydantic models for the Plans & Usage dashboard (F14, contract 8.2/8.4)."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from backend.schemas.plan import PlanResponse
from backend.schemas.store import SubscriptionResponse, UsageResponse


# ============== REQUEST SCHEMAS ==============

class SubscriptionChangeRequest(BaseModel):
    """Body for POST /api/v1/subscriptions (contract 8.2).

    `stripe_token` is optional: in mock-checkout mode (no STRIPE_SECRET_KEY configured)
    it is accepted but unused — the switch activates immediately. The real Stripe
    integration (PRD defers it to F-Payment) keeps the exact same request/response shape.
    """
    plan_code: str = Field(min_length=1, max_length=40)
    stripe_token: Optional[str] = Field(default=None, max_length=500)


# ============== RESPONSE SCHEMAS ==============

class SubscriptionChangeResponse(BaseModel):
    """POST /api/v1/subscriptions response: the new subscription + where the widget would redirect.

    `mode` is "mock" (immediate activation, the checkout_url is informational) or
    "stripe" (reserved for the F-Payment real integration — same contract).
    """
    subscription: SubscriptionResponse
    checkout_url: str
    mode: str


class PlansOverviewResponse(BaseModel):
    """GET /api/v1/dashboard/plans response (contract 8.4): everything the page renders."""
    current: SubscriptionResponse
    available: list[PlanResponse]
    usage: UsageResponse
