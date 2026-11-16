"""Store service — business logic for store creation, store info, and usage.

When a user creates their first store (FR-03):
1. A store row is inserted in platform.db.
2. A Free Trial subscription is auto-created.
3. The tenant_<slug>.db file is created lazily on first access (by the connection manager).
"""
from __future__ import annotations

import logging
import sqlite3

from backend.core.errors import ConflictError, NotFoundError
from backend.schemas.store import (
    StoreResponse,
    StoreWithSubscriptionResponse,
    SubscriptionResponse,
    UsageResponse,
    store_to_response,
    subscription_row_to_response,
)
from backend.shared.constants import PLAN_FREE_TRIAL, SUB_TRIAL
from database.connection import platform_session, tenant_session
from database.queries import (
    conversations as conversations_q,
    plans as plans_q,
    store_data as store_data_q,
    stores as stores_q,
    subscriptions as subscriptions_q,
    token_usage as token_usage_q,
)

logger = logging.getLogger("shop-assistant.store")


# ============== CREATE STORE ==============

def create_store(*, owner_user_id: int, slug: str, name: str) -> StoreWithSubscriptionResponse:
    """Creates a store + auto-creates a Free Trial subscription.

    Raises ConflictError if the user already has a store or the slug is taken.
    """
    with platform_session() as conn:
        # Check if user already has a store.
        existing = stores_q.get_store_by_owner(conn, owner_user_id)
        if existing is not None:
            raise ConflictError("You already have a store. Each account gets one store for now.")
        # Check slug uniqueness.
        if stores_q.get_store_by_slug(conn, slug) is not None:
            raise ConflictError(f"Store slug already taken: {slug}")
        # Get the Free Trial plan.
        plan = plans_q.get_plan_by_code(conn, PLAN_FREE_TRIAL)
        if plan is None:
            raise NotFoundError("Free Trial plan not found in catalog. Run init_db.py to seed plans.")
        # Create the store.
        try:
            store_id = stores_q.create_store(
                conn,
                owner_user_id=owner_user_id,
                slug=slug,
                name=name,
            )
        except sqlite3.IntegrityError as exc:
            raise ConflictError(f"Store slug already taken: {slug}") from exc
        # Auto-create the Free Trial subscription.
        subscriptions_q.create_subscription(
            conn,
            store_id=store_id,
            plan_id=int(plan["id"]),
            status=SUB_TRIAL,
        )
        # Re-fetch the store + subscription for the response.
        store_row = stores_q.get_store_by_id(conn, store_id)
        sub_row = subscriptions_q.get_active_subscription(conn, store_id)

    if store_row is None:
        raise NotFoundError("Store creation failed — row not found after insert.")
    if sub_row is None:
        raise NotFoundError("Subscription creation failed — row not found after insert.")

    # Touch the tenant DB so the file + schema are created now (not lazily on first chat).
    with tenant_session(store_row["slug"]):
        pass  # just opening it triggers the init.

    logger.info("Store created: id=%s slug=%s owner=%s", store_id, slug, owner_user_id)
    usage = _compute_usage(store_row, sub_row)
    return StoreWithSubscriptionResponse(
        store=store_to_response(dict(store_row)),
        subscription=subscription_row_to_response(sub_row),
        usage=usage,
    )


# ============== GET MY STORE ==============

def get_my_store(owner_user_id: int) -> StoreWithSubscriptionResponse:
    """Returns the current user's store + subscription + usage. Raises NotFoundError if no store."""
    result = get_my_store_optional(owner_user_id)
    if result is None:
        raise NotFoundError("You don't have a store yet. Create one to get started.")
    return result


def get_my_store_optional(owner_user_id: int) -> StoreWithSubscriptionResponse | None:
    """Same as get_my_store but returns None when the user has no store yet (dashboard probe)."""
    with platform_session() as conn:
        store_row = stores_q.get_store_by_owner(conn, owner_user_id)
        if store_row is None:
            return None
        sub_row = subscriptions_q.get_active_subscription(conn, int(store_row["id"]))

    if sub_row is None:
        raise NotFoundError("No active subscription found for your store.")

    usage = _compute_usage(store_row, sub_row)
    return StoreWithSubscriptionResponse(
        store=store_to_response(dict(store_row)),
        subscription=subscription_row_to_response(sub_row),
        usage=usage,
    )


# ============== USAGE ==============

def get_usage(store_id: int) -> UsageResponse:
    """Returns usage stats for the current month + plan limits."""
    with platform_session() as conn:
        store_row = stores_q.get_store_by_id(conn, store_id)
        if store_row is None:
            raise NotFoundError("Store not found.")
        sub_row = subscriptions_q.get_active_subscription(conn, store_id)
    if sub_row is None:
        raise NotFoundError("No active subscription found for this store.")
    return _compute_usage(store_row, sub_row)


# ============== INTERNAL HELPERS ==============

def _compute_usage(store_row, sub_row) -> UsageResponse:
    """Reads token/conversation/data counts from the tenant DB + plan limits from the subscription."""
    slug = str(store_row["slug"])
    with tenant_session(slug) as tconn:
        tokens_used = token_usage_q.get_month_tokens(tconn)
        conversations_used = conversations_q.count_started_this_month(tconn)
        data_used_kb = store_data_q.get_total_bytes(tconn) // 1024

    return UsageResponse(
        tokens_used=tokens_used,
        conversations_used=conversations_used,
        data_used_kb=data_used_kb,
        plan=subscription_row_to_response(sub_row).plan,
    )
