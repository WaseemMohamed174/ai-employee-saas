"""Complaints dashboard schemas — list response (F07, contract 8.4).

A complaint is a read-only view over `analyses` (is_complaint = 1) joined with
its message, conversation and customer — no dedicated table (per the ERD).
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


# ============== RESPONSE SCHEMAS ==============

class ComplaintListItem(BaseModel):
    """One row in the dashboard complaints table.

    message_excerpt = the analyzed assistant message; customer_message = the user
    message that triggered the complaint (what the owner actually wants to read).
    """
    analysis_id: int
    message_id: int
    conversation_id: int
    customer_external_id: str
    message_excerpt: str
    customer_message: Optional[str] = None
    sentiment: Optional[str] = None
    severity: Optional[str] = None
    sent_at: str


class ComplaintListResponse(BaseModel):
    items: list[ComplaintListItem]
    total: int
    page: int
    page_size: int
