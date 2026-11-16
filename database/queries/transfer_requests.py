"""Transfer request queries — writes on the `transfer_requests` table in tenant_<slug>.db.

A transfer is created only when the customer accepts the AI's offer (request_human=true)
or the AI decides one is needed. The store owner handles the actual human follow-up.
"""
from __future__ import annotations

import sqlite3


# ============== CREATE ==============

def create_transfer_request(
    conn: sqlite3.Connection,
    *,
    conversation_id: int,
    customer_id: int,
    reason: str | None = None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO transfer_requests (conversation_id, customer_id, reason, status)
        VALUES (?, ?, ?, 'pending')
        """,
        (conversation_id, customer_id, reason),
    )
    return int(cur.lastrowid)
