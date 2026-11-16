"""Plan schemas — Pydantic models for plan responses."""
from __future__ import annotations

from pydantic import BaseModel


# ============== RESPONSE SCHEMAS ==============

class PlanResponse(BaseModel):
    id: int
    code: str
    name: str
    data_limit_kb: int
    token_limit_month: int
    conversation_limit_month: int
    price_usd_cents: int
    price_usd_display: str  # e.g. "$19/mo" or "Free"
    is_trial: bool


class PlanListResponse(BaseModel):
    plans: list[PlanResponse]


# ============== MAPPING ==============

def plan_to_response(row: dict) -> PlanResponse:
    """Maps a plan dict (from a sqlite3.Row) to the PlanResponse schema."""
    price_cents = int(row["price_usd_cents"])
    if price_cents == 0:
        price_display = "Free"
    else:
        dollars = price_cents // 100
        cents = price_cents % 100
        price_display = f"${dollars}.{cents:02d}/mo"
    return PlanResponse(
        id=int(row["id"]),
        code=str(row["code"]),
        name=str(row["name"]),
        data_limit_kb=int(row["data_limit_kb"]),
        token_limit_month=int(row["token_limit_month"]),
        conversation_limit_month=int(row["conversation_limit_month"]),
        price_usd_cents=price_cents,
        price_usd_display=price_display,
        is_trial=bool(row["is_trial"]),
    )
