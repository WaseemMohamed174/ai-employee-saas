"""Violation queries — reads/writes on the `violations` and `violation_policies` tables.

The violations table stores every action the chat engine took against a customer
(F05); F08 reads it for the dashboard and adds policy management: the owner
configures one policy per action (warning / temp_ban / perma_ban) with a count
threshold inside a sliding window, and the chat engine escalates through it.
"""
from __future__ import annotations

import sqlite3
from typing import Optional


# ============== CREATE ==============

def create_violation(
    conn: sqlite3.Connection,
    *,
    customer_id: int,
    action: str,
    reason: Optional[str] = None,
    expires_at: Optional[str] = None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO violations (customer_id, action, reason, expires_at)
        VALUES (?, ?, ?, ?)
        """,
        (customer_id, action, reason, expires_at),
    )
    return int(cur.lastrowid)


def create_policy(
    conn: sqlite3.Connection,
    *,
    action: str,
    threshold_count: int,
    threshold_window_hours: int,
    auto_apply: bool,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO violation_policies (action, threshold_count, threshold_window_hours, auto_apply)
        VALUES (?, ?, ?, ?)
        """,
        (action, threshold_count, threshold_window_hours, int(auto_apply)),
    )
    return int(cur.lastrowid)


# ============== UPDATE ==============

def update_policy(
    conn: sqlite3.Connection,
    *,
    policy_id: int,
    threshold_count: int,
    threshold_window_hours: int,
    auto_apply: bool,
) -> None:
    conn.execute(
        """
        UPDATE violation_policies
        SET threshold_count = ?, threshold_window_hours = ?, auto_apply = ?
        WHERE id = ?
        """,
        (threshold_count, threshold_window_hours, int(auto_apply), policy_id),
    )


# ============== READ: VIOLATIONS ==============

def get_violations_paginated(
    conn: sqlite3.Connection,
    *,
    page: int = 1,
    page_size: int = 20,
    action: Optional[str] = None,
) -> tuple[list[sqlite3.Row], int]:
    """Returns (rows, total) for the violations dashboard table (F08).

    One row = one recorded violation joined with its customer. Most recent first;
    `action` optionally narrows to one action value (warning / temp_ban / perma_ban).
    """
    where = ""
    params: list[object] = []
    if action:
        where = "WHERE v.action = ?"
        params.append(action)
    total = conn.execute(
        f"SELECT COUNT(*) FROM violations v {where}",
        params,
    ).fetchone()[0]
    rows = conn.execute(
        f"""
        SELECT v.id, v.customer_id, cu.external_id AS customer_external_id,
               v.action, v.reason, v.created_at, v.expires_at
        FROM violations v
        JOIN customers cu ON cu.id = v.customer_id
        {where}
        ORDER BY v.created_at DESC, v.id DESC
        LIMIT ? OFFSET ?
        """,
        [*params, page_size, (page - 1) * page_size],
    ).fetchall()
    return rows, int(total)


def count_violations_in_window(
    conn: sqlite3.Connection,
    *,
    customer_id: int,
    window_hours: int,
) -> int:
    """How many violations this customer collected inside the last `window_hours`.

    Used by the chat engine BEFORE recording the current violation: the current
    one is the (count + 1)-th against the policy threshold.
    """
    row = conn.execute(
        """
        SELECT COUNT(*) FROM violations
        WHERE customer_id = ?
          AND created_at >= datetime('now', ?)
        """,
        (customer_id, f"-{int(window_hours)} hours"),
    ).fetchone()
    return int(row[0])


# ============== READ: POLICIES ==============

def list_policies(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """All configured policies, escalation order (warning, temp_ban, perma_ban)."""
    return conn.execute(
        """
        SELECT * FROM violation_policies
        ORDER BY CASE action WHEN 'warning' THEN 0 WHEN 'temp_ban' THEN 1 ELSE 2 END ASC
        """
    ).fetchall()


def get_auto_apply_policies(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Returns the store's auto-apply policies, most severe last (warning, temp_ban, perma_ban)."""
    return conn.execute(
        """
        SELECT * FROM violation_policies
        WHERE auto_apply = 1
        ORDER BY CASE action WHEN 'warning' THEN 0 WHEN 'temp_ban' THEN 1 ELSE 2 END ASC
        """
    ).fetchall()


def get_policy_by_action(conn: sqlite3.Connection, action: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM violation_policies WHERE action = ?",
        (action,),
    ).fetchone()
