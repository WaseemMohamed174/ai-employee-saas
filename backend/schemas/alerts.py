"""Alerts dashboard schemas — list + dismiss (F10, contract 8.4 + lifecycle 6.3).

An alert is one raised condition of the 4 R2.Q9 types (complaint_spike /
new_violation / token_near_limit / transfer_pending). Its state is the
`dismissed_at` stamp: NULL = active (the owner's to-do), set = dismissed
(handled, kept for the audit trail).
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


# ============== ALERT LIST SCHEMAS ==============

class AlertListItem(BaseModel):
    """One row in the dashboard alerts table."""
    id: int
    type: str
    severity: str
    message: str
    payload: Optional[str] = None
    created_at: str
    dismissed_at: Optional[str] = None


class AlertListResponse(BaseModel):
    items: list[AlertListItem]
    total: int
    page: int
    page_size: int


class AlertResponse(BaseModel):
    """The alert after an action (dismiss) — reflects the new state."""
    alert: AlertListItem
