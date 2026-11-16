"""Store data queries — reads/writes on the `store_data` table in tenant_<slug>.db.

Each item has an `item_id` (provided by the store, e.g. product SKU) and `content` (the raw text
the AI will search through). The content is stored as-is — no processing, no restructuring.
"""
from __future__ import annotations

import sqlite3
from typing import Optional


# ============== CREATE ==============

def create_item(
    conn: sqlite3.Connection,
    *,
    item_id: str,
    content: str,
    source: str = "api",
    upload_log_id: Optional[int] = None,
) -> int:
    """Inserts a single store_data row. Returns the row id."""
    cur = conn.execute(
        """
        INSERT INTO store_data (item_id, content, source, upload_log_id)
        VALUES (?, ?, ?, ?)
        """,
        (item_id, content, source, upload_log_id),
    )
    return int(cur.lastrowid)


def create_items(
    conn: sqlite3.Connection,
    *,
    items: list[dict],
    source: str = "api",
    upload_log_id: Optional[int] = None,
) -> list[int]:
    """Inserts multiple items. Each item dict must have `item_id` and `content`.
    Returns the list of inserted row ids."""
    row_ids = []
    for item in items:
        rid = create_item(
            conn,
            item_id=str(item["item_id"]),
            content=str(item["content"]),
            source=source,
            upload_log_id=upload_log_id,
        )
        row_ids.append(rid)
    return row_ids


# ============== READ ==============

def get_items_paginated(
    conn: sqlite3.Connection,
    *,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[sqlite3.Row], int]:
    """Returns (items, total_count) for the given page."""
    offset = (page - 1) * page_size
    rows = conn.execute(
        """
        SELECT id, item_id, content, source, upload_log_id, uploaded_at
        FROM store_data
        ORDER BY uploaded_at DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        (page_size, offset),
    ).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM store_data").fetchone()[0]
    return rows, int(total)


def get_item_by_id(conn: sqlite3.Connection, item_db_id: int) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM store_data WHERE id = ?",
        (item_db_id,),
    ).fetchone()


def get_total_bytes(conn: sqlite3.Connection) -> int:
    """Returns the total byte size of all content (SUM of LENGTH(content))."""
    row = conn.execute("SELECT COALESCE(SUM(LENGTH(content)), 0) FROM store_data").fetchone()
    return int(row[0]) if row else 0


def count_items(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) FROM store_data").fetchone()
    return int(row[0]) if row else 0


def get_items_for_search(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Returns (id, item_id, content) for every row in insertion order (RAG scan input)."""
    return conn.execute(
        "SELECT id, item_id, content FROM store_data ORDER BY id ASC"
    ).fetchall()
