"""Violations dashboard schemas — list + policy management (F08, contract 8.4).

A violation is a read-only view over the `violations` table joined with the
customer. A policy is one escalation step the store owner configures: when a
customer collects `threshold_count` violations inside `threshold_window_hours`
and `auto_apply` is on, the chat engine applies this policy's action.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


# ============== VIOLATION LIST SCHEMAS ==============

class ViolationListItem(BaseModel):
    """One row in the dashboard violations table."""
    id: int
    customer_id: int
    customer_external_id: str
    action: str
    reason: Optional[str] = None
    created_at: str
    expires_at: Optional[str] = None


class ViolationListResponse(BaseModel):
    items: list[ViolationListItem]
    total: int
    page: int
    page_size: int


# ============== POLICY SCHEMAS (FR-14) ==============

PolicyAction = Literal["warning", "temp_ban", "perma_ban"]

THRESHOLD_COUNT_MAX = 100
THRESHOLD_WINDOW_MAX_HOURS = 24 * 30


class ViolationPolicyCreate(BaseModel):
    """Create/update one escalation policy. Same action twice = upsert."""
    action: PolicyAction
    threshold_count: int = Field(default=1, ge=1, le=THRESHOLD_COUNT_MAX)
    threshold_window_hours: int = Field(default=24, ge=1, le=THRESHOLD_WINDOW_MAX_HOURS)
    auto_apply: bool = False


class ViolationPolicyItem(BaseModel):
    id: int
    action: str
    threshold_count: int
    threshold_window_hours: int
    auto_apply: bool
    created_at: str


class ViolationPolicyResponse(BaseModel):
    policy: ViolationPolicyItem


class ViolationPolicyListResponse(BaseModel):
    items: list[ViolationPolicyItem]
