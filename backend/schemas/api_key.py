"""API key schemas — Pydantic models for API key creation and listing."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ============== REQUEST SCHEMAS ==============

class ApiKeyCreateRequest(BaseModel):
    name: str = Field(default="default", min_length=1, max_length=50)


# ============== RESPONSE SCHEMAS ==============

class ApiKeyResponse(BaseModel):
    id: int
    name: str
    last_used_at: Optional[str] = None
    created_at: str
    revoked_at: Optional[str] = None
    # Only present on creation (the plain key is returned once, then never retrievable)
    key: Optional[str] = None


class ApiKeyListResponse(BaseModel):
    keys: list[ApiKeyResponse]


# ============== MAPPING ==============

def api_key_to_response(row, *, include_plain_key: Optional[str] = None) -> ApiKeyResponse:
    """Maps an api_keys row to ApiKeyResponse.

    `include_plain_key` is set only on creation — the plain key is returned once
    so the caller can display/copy it, then it's never retrievable again.
    """
    return ApiKeyResponse(
        id=int(row["id"]),
        name=str(row["name"]),
        last_used_at=row["last_used_at"],
        created_at=str(row["created_at"]),
        revoked_at=row["revoked_at"],
        key=include_plain_key,
    )
