"""Conversation queries — reads/writes on the `conversations` table in tenant_<slug>.db.

The plan's conversation_limit_month is enforced against conversations STARTED this month,
matching the same computation used by store_service._compute_usage for the usage display.
"""
from __future__ import annotations

import sqlite3
from typing import Optional


# ============== CREATE ==============

def create_conversation(conn: sqlite3.Connection, *, customer_id: int) -> int:
    cur = conn.execute(
        "INSERT INTO conversations (customer_id, status) VALUES (?, 'active')",
        (customer_id,),
    )
    return int(cur.lastrowid)


# ============== READ ==============

def get_conversation(conn: sqlite3.Connection, conversation_id: int) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM conversations WHERE id = ?",
        (conversation_id,),
    ).fetchone()


def get_conversations_paginated(
    conn: sqlite3.Connection,
    *,
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
) -> tuple[list[sqlite3.Row], int]:
    """Returns (rows, total) for the dashboard list (F06).

    Each row joins the customer (external_id + case_status), counts the messages and
    takes the last message's content as a preview. Most recent activity first.
    """
    where = "WHERE c.status = ?" if status else ""
    params: list[object] = [status] if status else []
    total = conn.execute(
        f"SELECT COUNT(*) FROM conversations c {where}",
        params,
    ).fetchone()[0]
    rows = conn.execute(
        f"""
        SELECT c.id, c.status, c.started_at, c.last_message_at,
               cu.external_id AS customer_external_id,
               cu.case_status AS case_status,
               (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) AS messages_count,
               (SELECT m.content FROM messages m WHERE m.conversation_id = c.id
                 ORDER BY m.id DESC LIMIT 1) AS last_message_preview
        FROM conversations c
        JOIN customers cu ON cu.id = c.customer_id
        {where}
        ORDER BY COALESCE(c.last_message_at, c.started_at) DESC, c.id DESC
        LIMIT ? OFFSET ?
        """,
        params + [page_size, (page - 1) * page_size],
    ).fetchall()
    return rows, int(total)


def count_started_this_month(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM conversations WHERE started_at >= date('now', 'start of month')"
    ).fetchone()
    return int(row[0]) if row else 0


# ============== UPDATE ==============

def touch_last_message(conn: sqlite3.Connection, conversation_id: int) -> None:
    conn.execute(
        "UPDATE conversations SET last_message_at = datetime('now') WHERE id = ?",
        (conversation_id,),
    )


def set_status(conn: sqlite3.Connection, conversation_id: int, status: str) -> None:
    """Updates the conversation status ('active' / 'transferred' — see CONVERSATION_STATUSES)."""
    conn.execute(
        "UPDATE conversations SET status = ? WHERE id = ?",
        (status, conversation_id),
    )
