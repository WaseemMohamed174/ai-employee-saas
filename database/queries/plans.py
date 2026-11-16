"""Plan queries — reads/writes on the `plans` catalog table.

The catalog is seeded by `database/seed_plans.py` from PRD section 4.1.
This module provides the read helpers used by the backend plan_service.
"""
from __future__ import annotations

import sqlite3
from typing import Optional


# ============== CREATE / UPSERT ==============

def upsert_plan(
    conn: sqlite3.Connection,
    *,
    code: str,
    name: str,
    data_limit_kb: int,
    token_limit_month: int,
    conversation_limit_month: int,
    price_usd_cents: int,
    is_trial: bool = False,
) -> int:
    """Inserts a plan, or updates it if the code already exists. Returns the row id."""
    cur = conn.execute(
        """
        INSERT INTO plans (code, name, data_limit_kb, token_limit_month, conversation_limit_month, price_usd_cents, is_trial)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(code) DO UPDATE SET
            name = excluded.name,
            data_limit_kb = excluded.data_limit_kb,
            token_limit_month = excluded.token_limit_month,
            conversation_limit_month = excluded.conversation_limit_month,
            price_usd_cents = excluded.price_usd_cents,
            is_trial = excluded.is_trial
        """,
        (code, name, data_limit_kb, token_limit_month, conversation_limit_month, price_usd_cents, 1 if is_trial else 0),
    )
    return int(cur.lastrowid)


# ============== READ ==============

def get_all_plans(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Returns all plans ordered by price ascending (free_trial first, then starter, pro, business)."""
    return conn.execute(
        """
        SELECT * FROM plans
        ORDER BY price_usd_cents ASC, id ASC
        """
    ).fetchall()


def get_plan_by_code(conn: sqlite3.Connection, code: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM plans WHERE code = ?",
        (code,),
    ).fetchone()


def get_plan_by_id(conn: sqlite3.Connection, plan_id: int) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM plans WHERE id = ?",
        (plan_id,),
    ).fetchone()
