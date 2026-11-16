"""Alert queries — reads/writes on the `alerts` table in tenant_<slug>.db.

Alerts are raised by the chat service (new_violation, transfer_pending, token_near_limit);
complaint_spike is computed by the alerts dashboard (F10, `_maybe_alert_complaint_spike`
in alerts_service) on every list call — the PRD 4.5 "period" rule with a spam guard.
"""
from __future__ import annotations

import sqlite3
from typing import Optional, Tuple


# ============== CREATE ==============

def create_alert(
    conn: sqlite3.Connection,
    *,
    type: str,
    message: str,
    severity: str = "info",
    payload: Optional[str] = None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO alerts (type, severity, message, payload)
        VALUES (?, ?, ?, ?)
        """,
        (type, severity, message, payload),
    )
    return int(cur.lastrowid)


# ============== READ ==============

def has_active_alert_of_type(conn: sqlite3.Connection, type: str) -> bool:
    """True when an undismissed alert of this type already exists (avoids alert spam)."""
    row = conn.execute(
        "SELECT 1 FROM alerts WHERE type = ? AND dismissed_at IS NULL LIMIT 1",
        (type,),
    ).fetchone()
    return row is not None


# ============== READ: DASHBOARD LIST (F10) ==============

def get_alerts_paginated(
    conn: sqlite3.Connection,
    *,
    page: int = 1,
    page_size: int = 20,
    type: Optional[str] = None,
    status: str = "all",
) -> Tuple[list[sqlite3.Row], int]:
    """Returns (rows, total) for the alerts dashboard table (F10).

    Newest first. `type` optionally narrows to one of the 4 R2.Q9 alert types;
    `status` narrows by the lifecycle 6.3 state: 'active' (undismissed only),
    'dismissed' (only stamped rows), or 'all' (default — dismissed rows stay
    visible with their dismissed_at for the audit trail).
    """
    clauses: list[str] = []
    params: list[object] = []
    if type:
        clauses.append("type = ?")
        params.append(type)
    if status == "active":
        clauses.append("dismissed_at IS NULL")
    elif status == "dismissed":
        clauses.append("dismissed_at IS NOT NULL")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    total = conn.execute(
        f"SELECT COUNT(*) FROM alerts {where}",
        params,
    ).fetchone()[0]
    rows = conn.execute(
        f"""
        SELECT id, type, severity, message, payload, created_at, dismissed_at
        FROM alerts
        {where}
        ORDER BY created_at DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        [*params, page_size, (page - 1) * page_size],
    ).fetchall()
    return rows, int(total)


def get_alert_by_id(conn: sqlite3.Connection, alert_id: int) -> Optional[sqlite3.Row]:
    """One alert row in the dashboard shape (404 source for dismiss)."""
    return conn.execute(
        "SELECT id, type, severity, message, payload, created_at, dismissed_at FROM alerts WHERE id = ?",
        (alert_id,),
    ).fetchone()


# ============== READ: COMPLAINT SPIKE WINDOW (F10) ==============

def complaint_analyses_in_window(
    conn: sqlite3.Connection,
    *,
    window_hours: int,
) -> Tuple[int, int]:
    """Returns (complaints, total) assistant-turn analyses inside the last `window_hours`.

    Every chat turn stores one `analyses` row attached to the assistant message; the
    complaint flag lives on the analysis. The window is measured on the assistant
    message's sent_at (analyses carry no own timestamp).
    """
    row = conn.execute(
        """
        SELECT
            SUM(a.is_complaint) AS complaints,
            COUNT(*) AS total
        FROM analyses a
        JOIN messages m ON m.id = a.message_id
        WHERE m.role = 'assistant'
          AND m.sent_at >= datetime('now', ?)
        """,
        (f"-{int(window_hours)} hours",),
    ).fetchone()
    total = int(row["total"] or 0)
    complaints = int(row["complaints"] or 0)
    return complaints, total


# ============== UPDATE: DISMISS (F10) ==============

def dismiss_alert(conn: sqlite3.Connection, *, alert_id: int) -> None:
    """Stamps dismissed_at (lifecycle 6.3: active → dismissed). The row stays —
    it is the audit trail; only the owner's to-do state is cleared. Idempotent:
    re-stamping an already-dismissed alert is a harmless no-op.
    """
    conn.execute(
        """
        UPDATE alerts
        SET dismissed_at = datetime('now')
        WHERE id = ? AND dismissed_at IS NULL
        """,
        (alert_id,),
    )
