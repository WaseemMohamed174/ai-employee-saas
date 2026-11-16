"""API key routes — create, list, revoke keys for the current user's store.

All routes require authentication. The store is resolved from the current user.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.core.deps import get_current_user
from backend.core.errors import ApiResponse, NotFoundError
from backend.schemas.api_key import ApiKeyCreateRequest
from backend.services import api_key_service, store_service
from database.connection import platform_session
from database.queries import stores as stores_q

router = APIRouter(prefix="/api/v1", tags=["api-keys"])


# ============== DEPENDENCY: resolve store_id from current user ==============

def _resolve_store_id(current_user: dict) -> int:
    """Returns the store_id for the current user. Raises NotFoundError if no store yet."""
    with platform_session() as conn:
        store = stores_q.get_store_by_owner(conn, int(current_user["id"]))
    if store is None:
        raise NotFoundError("You don't have a store yet. Create one first.")
    return int(store["id"])


# ============== CREATE API KEY ==============

@router.post("/api-keys")
def create_api_key(
    payload: ApiKeyCreateRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Create a new API key for the current user's store. Returns the plain key once."""
    store_id = _resolve_store_id(current_user)
    result = api_key_service.create_api_key(store_id=store_id, name=payload.name)
    return ApiResponse.ok(result.model_dump())


# ============== LIST API KEYS ==============

@router.get("/api-keys")
def list_api_keys(current_user: dict = Depends(get_current_user)) -> dict:
    """List all API keys for the current user's store (without plain keys)."""
    store_id = _resolve_store_id(current_user)
    keys = api_key_service.list_api_keys(store_id)
    return ApiResponse.ok({"keys": [k.model_dump() for k in keys]})


# ============== REVOKE API KEY ==============

@router.delete("/api-keys/{key_id}")
def revoke_api_key(
    key_id: int,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Revoke an API key by id."""
    store_id = _resolve_store_id(current_user)
    api_key_service.revoke_api_key(store_id=store_id, key_id=key_id)
    return ApiResponse.ok({"revoked": True, "key_id": key_id})
