"""API key service — create, list, revoke keys for a store.

Enforces the Free Trial limit (1 API key per store on the Free Trial plan).
The plain key is generated once, returned once, and only the hash is stored.
"""
from __future__ import annotations

import logging
import secrets

from backend.core.errors import ConflictError, ForbiddenError, NotFoundError
from backend.schemas.api_key import ApiKeyResponse, api_key_to_response
from database.connection import platform_session
from database.queries import (
    api_keys as api_keys_q,
    stores as stores_q,
    subscriptions as subscriptions_q,
)

logger = logging.getLogger("shop-assistant.api_key")


# ============== CREATE API KEY ==============

def create_api_key(*, store_id: int, name: str) -> ApiKeyResponse:
    """Creates a new API key. Returns the response with the plain key (shown once).

    Raises ForbiddenError if the store is on Free Trial and already has 1 active key.
    """
    with platform_session() as conn:
        # Verify the store exists.
        store = stores_q.get_store_by_id(conn, store_id)
        if store is None:
            raise NotFoundError("Store not found.")
        # Check the Free Trial limit.
        sub = subscriptions_q.get_active_subscription(conn, store_id)
        if sub is None:
            raise NotFoundError("No active subscription found for this store.")
        if sub["plan_is_trial"]:
            active_count = api_keys_q.count_active_keys(conn, store_id)
            if active_count >= 1:
                raise ForbiddenError(
                    "Free Trial allows only 1 API key. Upgrade to a paid plan to create more keys."
                )
        # Generate the plain key + hash.
        plain_key = secrets.token_urlsafe(32)
        key_hash = api_keys_q.hash_plain_key(plain_key)
        key_id = api_keys_q.create_api_key(
            conn,
            store_id=store_id,
            key_hash=key_hash,
            name=name,
        )
        # Re-fetch for the response.
        key_row = api_keys_q.get_api_key_by_id(conn, key_id, store_id)

    if key_row is None:
        raise NotFoundError("API key creation failed — row not found after insert.")
    logger.info("API key created: id=%s store=%s name=%s", key_id, store_id, name)
    return api_key_to_response(key_row, include_plain_key=plain_key)


# ============== LIST API KEYS ==============

def list_api_keys(store_id: int) -> list[ApiKeyResponse]:
    """Returns all API keys for the store (without plain keys)."""
    with platform_session() as conn:
        rows = api_keys_q.get_api_keys_by_store(conn, store_id)
    return [api_key_to_response(row) for row in rows]


# ============== REVOKE API KEY ==============

def revoke_api_key(*, store_id: int, key_id: int) -> None:
    """Revokes an API key. Raises NotFoundError if the key doesn't exist (or belongs to another store),
    or ConflictError if it's already revoked."""
    with platform_session() as conn:
        row = api_keys_q.get_api_key_by_id(conn, key_id, store_id)
        if row is None:
            raise NotFoundError("API key not found.")
        if row["revoked_at"] is not None:
            raise ConflictError("API key is already revoked.")
        api_keys_q.revoke_api_key(conn, key_id, store_id)
    logger.info("API key revoked: id=%s store=%s", key_id, store_id)
