"""Subscription queries — links a store to a plan with a status and lifecycle.

When a store is created (FR-03), a Free Trial subscription is auto-created.
Upgrades/cancellations are handled in F14 (Stripe integration).
"""
from __future__ import annotations

import sqlite3
from typing import Optional


# ============== CREATE ==============

def create_subscription(
    conn: sqlite3.Connection,
    *,
    store_id: int,
    plan_id: int,
    status: str = "trial",
) -> int:
    """Inserts a new subscription row."""
    cur = conn.execute(
        """
        INSERT INTO subscriptions (store_id, plan_id, status)
        VALUES (?, ?, ?)
        """,
        (store_id, plan_id, status),
    )
    return int(cur.lastrowid)


# ============== READ ==============

def get_active_subscription(conn: sqlite3.Connection, store_id: int) -> Optional[sqlite3.Row]:
    """Returns the most recent non-canceled subscription for the store."""
    return conn.execute(
        """
        SELECT s.*, p.code AS plan_code, p.name AS plan_name, p.is_trial AS plan_is_trial,
               p.data_limit_kb, p.token_limit_month, p.conversation_limit_month,
               p.price_usd_cents
        FROM subscriptions s
        JOIN plans p ON s.plan_id = p.id
        WHERE s.store_id = ? AND s.status IN ('trial', 'active')
        ORDER BY s.started_at DESC, s.id DESC
        LIMIT 1
        """,
        (store_id,),
    ).fetchone()


def get_subscription_by_id(conn: sqlite3.Connection, sub_id: int) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM subscriptions WHERE id = ?",
        (sub_id,),
    ).fetchone()


# ============== UPDATE ==============

def cancel_subscription(conn: sqlite3.Connection, sub_id: int) -> bool:
    cur = conn.execute(
        """
        UPDATE subscriptions
        SET status = 'canceled', canceled_at = datetime('now')
        WHERE id = ? AND status IN ('trial', 'active')
        """,
        (sub_id,),
    )
    return cur.rowcount > 0
