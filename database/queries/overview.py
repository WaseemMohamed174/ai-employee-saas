"""Overview queries — the aggregates behind GET /api/v1/dashboard/overview (F15).

All raw SQL for the overview lives here (CODE_RULES 6.3: queries written once,
multi-step writes inside a transaction). The service combines these tenant-db
aggregates with the platform-db API-key counts.
"""
from __future__ import annotations

import sqlite3

# The overview chart window: uploads_per_day covers the last 14 days (today included).
OVERVIEW_SERIES_DAYS = 14


# ============== TENANT-DB AGGREGATES ==============
# NOTE: items_total comes from store_data_q.count_items (written once, reused here).

def count_uploads(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) FROM data_upload_log").fetchone()
    return int(row[0]) if row else 0


def count_conversations(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()
    return int(row[0]) if row else 0


def count_complaints(conn: sqlite3.Connection) -> int:
    """Complaints are chat analyses flagged is_complaint=1 (the Complaints page's source)."""
    row = conn.execute("SELECT COUNT(*) FROM analyses WHERE is_complaint = 1").fetchone()
    return int(row[0]) if row else 0


def count_active_alerts(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM alerts WHERE dismissed_at IS NULL"
    ).fetchone()
    return int(row[0]) if row else 0


def uploads_per_day(conn: sqlite3.Connection, *, days: int = OVERVIEW_SERIES_DAYS) -> dict[str, int]:
    """Returns {YYYY-MM-DD: items_uploaded} for the days that have rows (UTC dates).

    The service zero-fills the full window so the chart always shows `days` points.
    """
    rows = conn.execute(
        """
        SELECT date(uploaded_at) AS day, COALESCE(SUM(item_count), 0) AS items
        FROM data_upload_log
        WHERE day >= date('now', ?)
        GROUP BY day
        ORDER BY day
        """,
        (f"-{days - 1} days",),
    ).fetchall()
    return {str(r["day"]): int(r["items"]) for r in rows}


def items_by_source(conn: sqlite3.Connection) -> dict[str, int]:
    """Items uploaded per source ('api' vs 'dashboard') — the donut chart's slices."""
    rows = conn.execute(
        """
        SELECT source, COALESCE(SUM(item_count), 0) AS items
        FROM data_upload_log
        GROUP BY source
        ORDER BY source
        """
    ).fetchall()
    return {str(r["source"]): int(r["items"]) for r in rows}


def recent_uploads(conn: sqlite3.Connection, *, limit: int = 5) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT id, source, item_count, file_size_bytes, uploaded_at
        FROM data_upload_log
        ORDER BY uploaded_at DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def recent_conversations(conn: sqlite3.Connection, *, limit: int = 5) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT id, status, started_at
        FROM conversations
        ORDER BY started_at DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def recent_alerts(conn: sqlite3.Connection, *, limit: int = 3) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT id, type, severity, created_at
        FROM alerts
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


# ============== PLATFORM-DB AGGREGATES ==============

def key_counts_for_store(conn: sqlite3.Connection, *, store_id: int) -> dict[str, int]:
    """Active vs revoked API keys for one store — the bar chart's two bars."""
    row = conn.execute(
        """
        SELECT
          COALESCE(SUM(CASE WHEN revoked_at IS NULL THEN 1 ELSE 0 END), 0) AS active,
          COALESCE(SUM(CASE WHEN revoked_at IS NOT NULL THEN 1 ELSE 0 END), 0) AS revoked
        FROM api_keys
        WHERE store_id = ?
        """,
        (store_id,),
    ).fetchone()
    return {"active": int(row["active"]), "revoked": int(row["revoked"])}
