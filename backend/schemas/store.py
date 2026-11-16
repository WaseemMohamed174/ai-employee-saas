"""Store schemas — Pydantic models for store creation, store info, and usage."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


# ============== REQUEST SCHEMAS ==============

class StoreCreateRequest(BaseModel):
    slug: str = Field(min_length=3, max_length=40, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
    name: str = Field(min_length=1, max_length=100)


# ============== RESPONSE SCHEMAS ==============

class StoreResponse(BaseModel):
    id: int
    slug: str
    name: str
    owner_user_id: int
    default_persona_id: Optional[int] = None
    created_at: str


class PlanLimitsResponse(BaseModel):
    plan_code: str
    plan_name: str
    plan_is_trial: bool
    data_limit_kb: int
    token_limit_month: int
    conversation_limit_month: int
    price_usd_cents: int


class SubscriptionResponse(BaseModel):
    id: int
    status: str
    started_at: str
    ends_at: Optional[str] = None
    canceled_at: Optional[str] = None
    plan: PlanLimitsResponse


class UsageResponse(BaseModel):
    tokens_used: int
    conversations_used: int
    data_used_kb: int
    plan: PlanLimitsResponse


class StoreWithSubscriptionResponse(BaseModel):
    store: StoreResponse
    subscription: SubscriptionResponse
    usage: UsageResponse


# ============== MAPPING ==============

def store_to_response(row: Any) -> StoreResponse:
    """Maps a store row (dict or sqlite3.Row) to StoreResponse."""
    return StoreResponse(
        id=int(row["id"]),
        slug=str(row["slug"]),
        name=str(row["name"]),
        owner_user_id=int(row["owner_user_id"]),
        default_persona_id=row["default_persona_id"],
        created_at=str(row["created_at"]),
    )


def subscription_row_to_response(row: Any) -> SubscriptionResponse:
    """Maps a subscription row (joined with plans) to SubscriptionResponse.

    The row must include the joined plan columns: plan_code, plan_name, plan_is_trial,
    data_limit_kb, token_limit_month, conversation_limit_month, price_usd_cents.
    """
    plan = PlanLimitsResponse(
        plan_code=str(row["plan_code"]),
        plan_name=str(row["plan_name"]),
        plan_is_trial=bool(row["plan_is_trial"]),
        data_limit_kb=int(row["data_limit_kb"]),
        token_limit_month=int(row["token_limit_month"]),
        conversation_limit_month=int(row["conversation_limit_month"]),
        price_usd_cents=int(row["price_usd_cents"]),
    )
    return SubscriptionResponse(
        id=int(row["id"]),
        status=str(row["status"]),
        started_at=str(row["started_at"]),
        ends_at=row["ends_at"],
        canceled_at=row["canceled_at"],
        plan=plan,
    )
