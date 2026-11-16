"""Subscription service — plan switching for the Plans & Usage dashboard (F14).

Mock checkout (client-approved, PRD defers real Stripe to F-Payment): when no
STRIPE_SECRET_KEY is configured the switch ACTIVATES IMMEDIATELY — the old
subscription is canceled (canceled_at stamped, row never deleted, audit trail
per lifecycle 6.3) and a new `active` subscription is created. Chats read the
plan limits live from the active subscription, so the new limits apply at once.
The request/response shape matches contract 8.2 exactly, so the real Stripe
integration slots in without contract changes (mode flips to "stripe").
"""
from __future__ import annotations

from backend.core.errors import ForbiddenError, NotFoundError, ValidationError
from backend.schemas.plan import PlanResponse, plan_to_response
from backend.schemas.store import SubscriptionResponse, UsageResponse
from backend.schemas.subscription import PlansOverviewResponse, SubscriptionChangeResponse
from backend.services import store_service
from backend.shared.constants import SUB_ACTIVE
from database.connection import platform_session
from database.queries import plans as plans_q
from database.queries import subscriptions as subscriptions_q


# ============== PLANS OVERVIEW (GET /api/v1/dashboard/plans) ==============

def get_plans_overview(owner_user_id: int) -> PlansOverviewResponse:
    """Everything the Plans & Usage page renders: current subscription, paid catalog, usage."""
    my = store_service.get_my_store(owner_user_id)  # NotFoundError when no store / no sub
    with platform_session() as conn:
        rows = plans_q.get_all_plans(conn)
    paid = [plan_to_response(dict(r)) for r in rows if not bool(r["is_trial"])]
    paid.sort(key=lambda p: p.price_usd_cents)
    return PlansOverviewResponse(
        current=my.subscription,
        available=paid,
        usage=UsageResponse(
            tokens_used=my.usage.tokens_used,
            conversations_used=my.usage.conversations_used,
            data_used_kb=my.usage.data_used_kb,
            plan=my.usage.plan,
        ),
    )


# ============== CHANGE SUBSCRIPTION (POST /api/v1/subscriptions) ==============

def change_subscription(owner_user_id: int, plan_code: str, stripe_token: str | None) -> SubscriptionChangeResponse:
    """Switches the store's plan via mock checkout (immediate activation).

    403 when the user has no store yet; 422 for an unknown plan, the free_trial
    target (the trial is the starting tier, not a switch target) and re-subscribing
    to the plan already active.
    """
    with platform_session() as conn:
        store_row = _store_row_for_owner(conn, owner_user_id)
        plan_row = plans_q.get_plan_by_code(conn, plan_code)
        if plan_row is None:
            raise ValidationError(f"Unknown plan code: {plan_code}")
        if bool(plan_row["is_trial"]):
            raise ValidationError("free_trial is the starting tier — pick a paid plan to switch to.")
        sub_row = subscriptions_q.get_active_subscription(conn, int(store_row["id"]))
        if sub_row is None:
            raise NotFoundError("No active subscription found for your store.")
        if str(sub_row["plan_code"]) == plan_code:
            raise ValidationError(f"Your store is already on the {plan_row['name']} plan.")
        # Mock checkout: stamp the old row (audit trail) and activate the new one now.
        subscriptions_q.cancel_subscription(conn, int(sub_row["id"]))
        new_id = subscriptions_q.create_subscription(
            conn,
            store_id=int(store_row["id"]),
            plan_id=int(plan_row["id"]),
            status=SUB_ACTIVE,
        )
        fresh = subscriptions_q.get_subscription_by_id(conn, new_id)
        if fresh is None:  # pragma: no cover — create just returned this id
            raise NotFoundError("Subscription vanished right after creation.")
        fresh_with_plan = subscriptions_q.get_active_subscription(conn, int(store_row["id"]))
        if fresh_with_plan is None or int(fresh_with_plan["id"]) != new_id:  # pragma: no cover
            raise NotFoundError("The new subscription is not active.")

    checkout_url = f"/dashboard/plans?checkout=mock&plan={plan_code}"
    if stripe_token:
        # The token is accepted for contract parity; mock mode never calls Stripe.
        checkout_url += "&token=accepted"
    return SubscriptionChangeResponse(
        subscription=subscription_response_from_row(dict(fresh_with_plan)),
        checkout_url=checkout_url,
        mode="mock",
    )


# ============== INTERNAL HELPERS ==============

def _store_row_for_owner(conn, owner_user_id: int):
    """The owner's store row; ForbiddenError mirrors store_service's no-store semantics."""
    from database.queries import stores as stores_q

    store_row = stores_q.get_store_by_owner(conn, owner_user_id)
    if store_row is None:
        raise ForbiddenError("You don't have a store yet. Create one to manage plans.")
    return store_row


def subscription_response_from_row(row: dict) -> SubscriptionResponse:
    """Maps a joined subscription+plan row (subscriptions_q) to the response schema."""
    return SubscriptionResponse(
        id=int(row["id"]),
        status=str(row["status"]),
        started_at=str(row["started_at"]),
        ends_at=row["ends_at"],
        canceled_at=row["canceled_at"],
        plan=_plan_limits_from_row(row),
    )


def _plan_limits_from_row(row: dict):
    """The PlanLimitsResponse nested in a joined subscription row (shared shape with store_service)."""
    from backend.schemas.store import PlanLimitsResponse

    return PlanLimitsResponse(
        plan_code=str(row["plan_code"]),
        plan_name=str(row["plan_name"]),
        plan_is_trial=bool(row["plan_is_trial"]),
        data_limit_kb=int(row["data_limit_kb"]),
        token_limit_month=int(row["token_limit_month"]),
        conversation_limit_month=int(row["conversation_limit_month"]),
        price_usd_cents=int(row["price_usd_cents"]),
    )
