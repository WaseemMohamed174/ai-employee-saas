"""Customers dashboard schemas — list + unban (F09, contract 8.4).

A customer is the store's chat customer (created on first contact), and
`case_status` is its lifecycle per state machine 6.1 (active / analyzing /
warned / banned / transferred). The dashboard lists them with the violation
count and lets the owner unban banned ones (FR-15).
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


# ============== CUSTOMER LIST SCHEMAS ==============

class CustomerListItem(BaseModel):
    """One row in the dashboard customers table."""
    id: int
    external_id: str
    case_status: str
    first_seen_at: str
    banned_at: Optional[str] = None
    banned_reason: Optional[str] = None
    violation_count: int = 0


class CustomerListResponse(BaseModel):
    items: list[CustomerListItem]
    total: int
    page: int
    page_size: int


class CustomerResponse(BaseModel):
    """The customer after an action (unban) — reflects the new state."""
    customer: CustomerListItem
