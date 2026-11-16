"""Alerts service — dashboard list + dismiss for the store owner (F10, FR-13/R2.Q9).

Read/write over the tenant DB with the same tenant isolation as the customers
service (platform lookup for the slug, then the tenant DB). The list call first
evaluates `complaint_spike` (PRD 4.5, the one dashboard-computed alert type):
enough assistant-turn analyses inside the window and a complaint ratio over the
threshold raise ONE spike alert — the has_active_alert_of_type guard keeps it
at one until the owner dismisses it. Dismiss is the one write path: it stamps
`dismissed_at` (lifecycle 6.3); the row stays as the audit trail.
"""
from __future__ import annotations

import json
import logging

from backend.core.errors import ForbiddenError, NotFoundError
from backend.schemas.alerts import (
    AlertListItem,
    AlertListResponse,
    AlertResponse,
)
from backend.shared import constants as C
from backend.shared.store_access import tenant_session_for_store
from database.queries import alerts as alerts_q

logger = logging.getLogger("shop-assistant.alerts")


# ============== ALERTS LIST ==============

def list_alerts(
    *,
    store_id: int,
    page: int = 1,
    page_size: int = 20,
    type: str | None = None,
    status: str = C.ALERT_STATUS_ALL,
) -> AlertListResponse:
    """Returns paginated alerts for the dashboard table (complaint_spike evaluated first)."""
    if store_id <= 0:
        raise ForbiddenError("Store not found.")
    with tenant_session_for_store(store_id) as tconn:
        _maybe_alert_complaint_spike(tconn)
        rows, total = alerts_q.get_alerts_paginated(
            tconn, page=page, page_size=page_size, type=type, status=status,
        )
    return AlertListResponse(
        items=[_row_to_item(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


def _row_to_item(row) -> AlertListItem:  # noqa: ANN001 — sqlite3.Row
    return AlertListItem(
        id=int(row["id"]),
        type=str(row["type"]),
        severity=str(row["severity"]),
        message=str(row["message"]),
        payload=row["payload"],
        created_at=str(row["created_at"]),
        dismissed_at=row["dismissed_at"],
    )


# ============== DISMISS (lifecycle 6.3) ==============

def dismiss_alert(*, store_id: int, alert_id: int) -> AlertResponse:
    """Stamps dismissed_at on one alert (active → dismissed, lifecycle 6.3).

    404 when the alert does not belong to this store (or does not exist —
    the tenant DB makes both the same). Idempotent: dismissing an
    already-dismissed alert is a no-op that returns the current state.
    """
    if store_id <= 0:
        raise ForbiddenError("Store not found.")
    with tenant_session_for_store(store_id) as tconn:
        row = alerts_q.get_alert_by_id(tconn, alert_id)
        if row is None:
            raise NotFoundError("Alert not found.")
        alerts_q.dismiss_alert(tconn, alert_id=alert_id)
        fresh = alerts_q.get_alert_by_id(tconn, alert_id)
        assert fresh is not None, "alert row vanished inside its own transaction"
    logger.info("store %s dismissed alert %s (type=%s)", store_id, alert_id, str(fresh["type"]))
    return AlertResponse(alert=_row_to_item(fresh))


# ============== COMPLAINT SPIKE (PRD 4.5, dashboard-computed) ==============

def _maybe_alert_complaint_spike(conn) -> None:  # noqa: ANN001 — sqlite3.Connection
    """Raises the complaint_spike alert when the window's complaint ratio crosses the rule.

    PRD 4.5: "the complaint ratio rose above the threshold over a given period". Deterministic rule
    (constants, F10): the last COMPLAINT_SPIKE_WINDOW_HOURS hours carry at least
    COMPLAINT_SPIKE_MIN_ANALYSES assistant-turn analyses AND complaints/total
    (rounded to the nearest percent) reaches COMPLAINT_SPIKE_RATIO_PERCENT. ONE alert
    per active spike — the has_active guard re-arms only after the owner dismisses
    the previous one.
    """
    complaints, total = alerts_q.complaint_analyses_in_window(
        conn, window_hours=C.COMPLAINT_SPIKE_WINDOW_HOURS,
    )
    if total < C.COMPLAINT_SPIKE_MIN_ANALYSES or complaints <= 0:
        return
    # Standard rounding (2/3 = 67%), matching PRD 4.5's percentage semantics — floor
    # division reported 66% for the same spike and the tests/PRD say 67.
    ratio_percent = round(complaints * 100 / total)
    if ratio_percent < C.COMPLAINT_SPIKE_RATIO_PERCENT:
        return
    if alerts_q.has_active_alert_of_type(conn, C.ALERT_COMPLAINT_SPIKE):
        return
    payload = json.dumps({
        "window_hours": C.COMPLAINT_SPIKE_WINDOW_HOURS,
        "analyses": total,
        "complaints": complaints,
        "ratio_percent": ratio_percent,
    }, separators=(",", ":"))
    alerts_q.create_alert(
        conn,
        type=C.ALERT_COMPLAINT_SPIKE,
        severity=C.ALERT_SEVERITY_WARNING,
        message=(
            f"Complaint spike: {complaints} of the last {total} chats "
            f"({ratio_percent}%) are complaints within {C.COMPLAINT_SPIKE_WINDOW_HOURS}h."
        ),
        payload=payload,
    )
    logger.info("complaint_spike raised: %d/%d (%d%%) in the last %dh",
                complaints, total, ratio_percent, C.COMPLAINT_SPIKE_WINDOW_HOURS)
