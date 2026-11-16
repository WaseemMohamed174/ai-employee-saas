"""Overview schemas — Pydantic models for the dashboard Overview page (F15, FR-13).

Contract 8.4:
- GET /api/v1/dashboard/overview → {stats, uploads_per_day, items_by_source,
  keys_by_status, recent_uploads, recent_conversations, recent_alerts}
"""
from __future__ import annotations

from pydantic import BaseModel


# ============== RESPONSE SCHEMAS ==============

class OverviewStats(BaseModel):
    """The stat cards row. AI-driven counters (conversations/complaints/alerts) are
    honest zeros on a fresh store — they grow as the widget chats."""
    items_total: int
    bytes_total: int
    uploads_count: int
    keys_active: int
    keys_revoked: int
    conversations_total: int
    complaints_total: int
    alerts_active: int


class UploadDayPoint(BaseModel):
    """One day of the uploads area chart (UTC dates, exactly 14 points ascending)."""
    day: str
    items: int


class RecentUpload(BaseModel):
    id: int
    source: str
    item_count: int
    file_size_bytes: int
    uploaded_at: str


class RecentConversation(BaseModel):
    id: int
    status: str
    started_at: str


class RecentAlert(BaseModel):
    id: int
    type: str
    severity: str
    created_at: str


class OverviewResponse(BaseModel):
    """The whole Overview page in one response (one GET renders everything — the same
    one-source-of-truth rule as the System Status page)."""
    stats: OverviewStats
    uploads_per_day: list[UploadDayPoint]
    items_by_source: dict[str, int]
    keys_by_status: dict[str, int]
    recent_uploads: list[RecentUpload]
    recent_conversations: list[RecentConversation]
    recent_alerts: list[RecentAlert]
