"""Message queries — reads/writes on the `messages` table in tenant_<slug>.db.

Roles: 'user' (store customer) and 'assistant' (the AI reply).
`ai_decision_raw` keeps the raw provider JSON for the dashboard detail view (F06).
"""
from __future__ import annotations

import sqlite3
from typing import Optional


# ============== CREATE ==============

def create_message(
    conn: sqlite3.Connection,
    *,
    conversation_id: int,
    role: str,
    content: str,
    store_data_id: Optional[int] = None,
    ai_decision_raw: Optional[str] = None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO messages (conversation_id, role, content, store_data_id, ai_decision_raw)
        VALUES (?, ?, ?, ?, ?)
        """,
        (conversation_id, role, content, store_data_id, ai_decision_raw),
    )
    return int(cur.lastrowid)


# ============== READ ==============

def get_conversation_messages(
    conn: sqlite3.Connection,
    *,
    conversation_id: int,
    limit: int = 500,
) -> list[sqlite3.Row]:
    """Returns the conversation's LAST `limit` messages in chronological order (oldest first)."""
    rows = conn.execute(
        """
        SELECT * FROM messages
        WHERE conversation_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (conversation_id, limit),
    ).fetchall()
    rows.reverse()
    return rows


def list_conversation_messages(
    conn: sqlite3.Connection,
    *,
    conversation_id: int,
) -> list[sqlite3.Row]:
    """Returns ALL the conversation's messages in chronological order (oldest first, no limit)."""
    return conn.execute(
        "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id ASC",
        (conversation_id,),
    ).fetchall()
