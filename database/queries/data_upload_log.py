"""Data upload log queries — audit trail for every data upload operation.

Every upload (via API or dashboard) creates one row here, recording:
- source: 'api' or 'dashboard'
- item_count: how many items were inserted
- file_size_bytes: total byte size of the uploaded content
- uploaded_by_user_id: the user who performed the upload (None for API uploads)
"""
from __future__ import annotations

import sqlite3


# ============== CREATE ==============

def create_log(
    conn: sqlite3.Connection,
    *,
    source: str,
    item_count: int,
    file_size_bytes: int,
    uploaded_by_user_id: int | None = None,
) -> int:
    """Inserts a new upload log entry. Returns the log id."""
    cur = conn.execute(
        """
        INSERT INTO data_upload_log (source, item_count, file_size_bytes, uploaded_by_user_id)
        VALUES (?, ?, ?, ?)
        """,
        (source, item_count, file_size_bytes, uploaded_by_user_id),
    )
    return int(cur.lastrowid)


# ============== READ ==============

def get_logs_paginated(
    conn: sqlite3.Connection,
    *,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[sqlite3.Row], int]:
    """Returns (logs, total_count) for the given page."""
    offset = (page - 1) * page_size
    rows = conn.execute(
        """
        SELECT id, source, item_count, file_size_bytes, uploaded_by_user_id, uploaded_at
        FROM data_upload_log
        ORDER BY uploaded_at DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        (page_size, offset),
    ).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM data_upload_log").fetchone()[0]
    return rows, int(total)


def count_logs(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) FROM data_upload_log").fetchone()
    return int(row[0]) if row else 0
