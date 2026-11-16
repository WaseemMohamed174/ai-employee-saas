"""Analysis queries — reads/writes on the `analyses` table in tenant_<slug>.db.

One analysis per assistant message: sentiment + complaint/violation flags
(detected by the AI provider, parsed in the adapter). The complaints dashboard
(F07) reads this table as a view: every row with is_complaint = 1 is one complaint.
"""
from __future__ import annotations

import sqlite3


# ============== CREATE ==============

def create_analysis(
    conn: sqlite3.Connection,
    *,
    message_id: int,
    sentiment: str,
    is_complaint: bool,
    is_violation: bool,
    violation_type: str | None = None,
    severity: str | None = None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO analyses (message_id, sentiment, is_complaint, is_violation, violation_type, severity)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (message_id, sentiment, int(is_complaint), int(is_violation), violation_type, severity),
    )
    return int(cur.lastrowid)


# ============== READ ==============

def get_analyses_by_message_ids(
    conn: sqlite3.Connection,
    message_ids: list[int],
) -> dict[int, sqlite3.Row]:
    """Returns {message_id: analysis_row} for the given message ids (empty input → empty dict)."""
    if not message_ids:
        return {}
    placeholders = ",".join("?" for _ in message_ids)
    rows = conn.execute(
        f"SELECT * FROM analyses WHERE message_id IN ({placeholders})",
        message_ids,
    ).fetchall()
    return {int(row["message_id"]): row for row in rows}


# ============== READ (F07 complaints dashboard) ==============

def get_complaints_paginated(
    conn: sqlite3.Connection,
    *,
    page: int = 1,
    page_size: int = 20,
    sentiment: str | None = None,
) -> tuple[list[sqlite3.Row], int]:
    """Returns (rows, total) for the complaints dashboard table (F07).

    One complaint = one analysis row with is_complaint = 1, joined with its message
    (content + conversation) and the customer. `customer_message` carries the user
    message that triggered the complaint (the analysis itself lives on the assistant
    message). Most recent message first.
    `sentiment` optionally narrows to one sentiment value.
    """
    where = "WHERE a.is_complaint = 1"
    params: list[object] = []
    if sentiment:
        where += " AND a.sentiment = ?"
        params.append(sentiment)
    total = conn.execute(
        f"SELECT COUNT(*) FROM analyses a {where}",
        params,
    ).fetchone()[0]
    rows = conn.execute(
        f"""
        SELECT a.id AS analysis_id, a.message_id, a.sentiment, a.severity,
               m.conversation_id, m.content, m.sent_at,
               cu.external_id AS customer_external_id,
               (SELECT mu.content FROM messages mu
                 WHERE mu.conversation_id = m.conversation_id AND mu.id < m.id AND mu.role = 'user'
                 ORDER BY mu.id DESC LIMIT 1) AS customer_message
        FROM analyses a
        JOIN messages m ON m.id = a.message_id
        JOIN conversations c ON c.id = m.conversation_id
        JOIN customers cu ON cu.id = c.customer_id
        {where}
        ORDER BY m.sent_at DESC, a.id DESC
        LIMIT ? OFFSET ?
        """,
        params + [page_size, (page - 1) * page_size],
    ).fetchall()
    return rows, int(total)
