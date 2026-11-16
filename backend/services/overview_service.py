"""Overview service — the dashboard Overview page (F15, FR-13).

One read-only GET that assembles everything the page renders: the stat cards,
the 14-day uploads series (zero-filled so the chart never lies about missing
days), the items-by-source donut, the API-keys bar, and the recent-activity
lists. Aggregates come exclusively from database/queries/overview.py (plus the
existing store_data bytes query) — no business SQL in the service layer.

Design decisions (F15 Plan):
- One response renders the whole page: the stat numbers, the charts and the
  recent lists can never disagree with each other (F12's rule, again).
- The uploads series covers exactly the last 14 UTC days ascending, zero-filled;
  `day` strings come from SQLite's date() so chart labels and SQL agree.
- AI-driven counters (conversations / complaints / alerts) are honest zeros on a
  fresh store — they are real aggregates, not placeholders.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.core.errors import ForbiddenError
from backend.schemas.overview import (
    OverviewResponse,
    OverviewStats,
    RecentAlert,
    RecentConversation,
    RecentUpload,
    UploadDayPoint,
)
from database.connection import platform_session, tenant_session
from database.queries import overview as overview_q
from database.queries import stores as stores_q
from database.queries import store_data as store_data_q


def get_overview(*, store_id: int) -> OverviewResponse:
    """Builds the whole Overview payload for one store."""
    if store_id <= 0:
        raise ForbiddenError("Store not found.")

    # Resolve the slug once (the tenant file is named after it).
    with platform_session() as pconn:
        store = stores_q.get_store_by_id(pconn, store_id)
        if store is None:
            raise ForbiddenError("Store not found.")
        keys = overview_q.key_counts_for_store(pconn, store_id=store_id)
    slug = str(store["slug"])

    with tenant_session(slug) as tconn:
        items_total = store_data_q.count_items(tconn)
        bytes_total = store_data_q.get_total_bytes(tconn)
        uploads_count = overview_q.count_uploads(tconn)
        conversations_total = overview_q.count_conversations(tconn)
        complaints_total = overview_q.count_complaints(tconn)
        alerts_active = overview_q.count_active_alerts(tconn)
        per_day = overview_q.uploads_per_day(tconn)
        by_source = overview_q.items_by_source(tconn)
        uploads_rows = overview_q.recent_uploads(tconn)
        convo_rows = overview_q.recent_conversations(tconn)
        alert_rows = overview_q.recent_alerts(tconn)

    # Zero-fill the 14-day window ascending (today last) so the chart's x-axis is stable.
    today = datetime.now(timezone.utc).date()
    series: list[UploadDayPoint] = []
    for offset in range(overview_q.OVERVIEW_SERIES_DAYS - 1, -1, -1):
        day = (today - timedelta(days=offset)).isoformat()
        series.append(UploadDayPoint(day=day, items=int(per_day.get(day, 0))))

    return OverviewResponse(
        stats=OverviewStats(
            items_total=items_total,
            bytes_total=int(bytes_total),
            uploads_count=uploads_count,
            keys_active=keys["active"],
            keys_revoked=keys["revoked"],
            conversations_total=conversations_total,
            complaints_total=complaints_total,
            alerts_active=alerts_active,
        ),
        uploads_per_day=series,
        items_by_source=by_source,
        keys_by_status=keys,
        recent_uploads=[
            RecentUpload(
                id=int(r["id"]),
                source=str(r["source"]),
                item_count=int(r["item_count"]),
                file_size_bytes=int(r["file_size_bytes"]),
                uploaded_at=str(r["uploaded_at"]),
            )
            for r in uploads_rows
        ],
        recent_conversations=[
            RecentConversation(
                id=int(r["id"]),
                status=str(r["status"]),
                started_at=str(r["started_at"]),
            )
            for r in convo_rows
        ],
        recent_alerts=[
            RecentAlert(
                id=int(r["id"]),
                type=str(r["type"]),
                severity=str(r["severity"]),
                created_at=str(r["created_at"]),
            )
            for r in alert_rows
        ],
    )
