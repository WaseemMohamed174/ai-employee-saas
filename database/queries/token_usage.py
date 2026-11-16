"""Token usage queries — writes/reads on the `token_usage` table in tenant_<slug>.db.

Tracks per-message consumption so the plan's token_limit_month and the
token_near_limit alert (90% of the plan limit) can be computed.
"""
from __future__ import annotations

import sqlite3


# ============== CREATE ==============

def record_usage(
    conn: sqlite3.Connection,
    *,
    message_id: int,
    prompt_tokens: int,
    completion_tokens: int,
    cost_usd_micros: int = 0,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO token_usage (message_id, prompt_tokens, completion_tokens, total_tokens, cost_usd_micros)
        VALUES (?, ?, ?, ?, ?)
        """,
        (message_id, prompt_tokens, completion_tokens, prompt_tokens + completion_tokens, cost_usd_micros),
    )
    return int(cur.lastrowid)


# ============== READ ==============

def get_month_tokens(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COALESCE(SUM(total_tokens), 0) FROM token_usage WHERE recorded_at >= date('now', 'start of month')"
    ).fetchone()
    return int(row[0]) if row else 0
