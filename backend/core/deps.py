"""FastAPI dependencies — reusable callables for dependency injection.

Per CODE_RULES 6.2: routes receive the request and return the response; business logic
lives in services. Dependencies like `get_current_user` bridge the two.
"""
from __future__ import annotations

from typing import Optional

from fastapi import Header

from backend.core.errors import UnauthorizedError
from backend.core.security import decode_access_token, extract_bearer_token
from database.connection import platform_session
from database.queries import api_keys as api_keys_q
from database.queries import stores as stores_q
from database.queries import users as users_q


# ============== CURRENT USER DEPENDENCY (JWT) ==============

def get_current_user(authorization: Optional[str] = Header(default=None)) -> dict:
    """FastAPI dependency: extracts and validates the Bearer token, returns the user row.

    Raises UnauthorizedError if the token is missing, invalid, or the user no longer exists.
    """
    token = extract_bearer_token(authorization)
    payload = decode_access_token(token)
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise UnauthorizedError("Token missing subject")
    try:
        user_id = int(user_id_str)
    except ValueError as exc:
        raise UnauthorizedError("Token subject is not a valid user id") from exc

    with platform_session() as conn:
        user = users_q.get_user_by_id(conn, user_id)
    if user is None:
        raise UnauthorizedError("User not found")
    return dict(user)


def get_optional_user(authorization: Optional[str] = Header(default=None)) -> Optional[dict]:
    """Like get_current_user but returns None instead of raising when no token is present."""
    if not authorization:
        return None
    try:
        return get_current_user(authorization=authorization)
    except UnauthorizedError:
        return None


# ============== CURRENT STORE DEPENDENCY (from JWT user) ==============

def get_current_store_id(current_user: dict = Header(default=None, alias="Authorization")) -> int:
    """Resolves the store_id for the current user. Actually uses get_current_user internally.

    Note: FastAPI doesn't easily chain Header-based deps, so we use a simpler approach:
    the route depends on get_current_user, then calls _resolve_store_id(current_user).
    This dependency is kept for documentation but the actual resolution happens in the route.
    """
    raise NotImplementedError("Use _resolve_store_id(get_current_user()) in the route instead.")


def _resolve_store_id(current_user: dict) -> int:
    """Returns the store_id for the current user. Raises NotFoundError if no store yet."""
    from backend.core.errors import NotFoundError
    with platform_session() as conn:
        store = stores_q.get_store_by_owner(conn, int(current_user["id"]))
    if store is None:
        raise NotFoundError("You don't have a store yet. Create one first.")
    return int(store["id"])


# ============== API KEY DEPENDENCY (for public chat/data API) ==============

def get_current_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")) -> dict:
    """FastAPI dependency: authenticates via the X-API-Key header.

    Returns a dict with `api_key` (the row) and `store` (the store row).
    Raises UnauthorizedError if the key is missing, invalid, or revoked.
    """
    if not x_api_key:
        raise UnauthorizedError("Missing X-API-Key header")
    key_hash = api_keys_q.hash_plain_key(x_api_key)
    with platform_session() as conn:
        key_row = api_keys_q.get_api_key_by_hash(conn, key_hash)
        if key_row is None:
            raise UnauthorizedError("Invalid or revoked API key")
        store_row = stores_q.get_store_by_id(conn, int(key_row["store_id"]))
    if store_row is None:
        raise UnauthorizedError("API key points to a missing store")
    # Update last_used_at (best effort, non-blocking).
    with platform_session() as conn:
        api_keys_q.touch_last_used(conn, int(key_row["id"]))
    return {"api_key": dict(key_row), "store": dict(store_row)}
