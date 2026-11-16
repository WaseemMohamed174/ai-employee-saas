"""Customer queries — reads/writes on the `customers` table in tenant_<slug>.db.

A customer is a store's chat customer, identified by the store's own external id.
case_status follows WORKFLOW 6.1: active / analyzing / warned / banned / transferred.
"""
from __future__ import annotations

import sqlite3
from typing import Optional


# ============== READ ==============

def get_customer_by_external_id(conn: sqlite3.Connection, external_id: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM customers WHERE external_id = ? ORDER BY id LIMIT 1",
        (external_id,),
    ).fetchone()


def get_customer_by_id(conn: sqlite3.Connection, customer_id: int) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM customers WHERE id = ?",
        (customer_id,),
    ).fetchone()


# ============== READ: DASHBOARD LIST (F09) ==============

def get_customers_paginated(
    conn: sqlite3.Connection,
    *,
    page: int = 1,
    page_size: int = 20,
    case_status: Optional[str] = None,
) -> tuple[list[sqlite3.Row], int]:
    """Returns (rows, total) for the customers dashboard table (F09).

    One row = one chat customer with its violation count (LEFT JOIN — 0 for clean
    customers). Most recent first; `case_status` optionally narrows to one lifecycle
    value (active / analyzing / warned / banned / transferred).
    """
    where = ""
    params: list[object] = []
    if case_status:
        where = "WHERE cu.case_status = ?"
        params.append(case_status)
    total = conn.execute(
        f"SELECT COUNT(*) FROM customers cu {where}",
        params,
    ).fetchone()[0]
    rows = conn.execute(
        f"""
        SELECT cu.id, cu.external_id, cu.case_status, cu.first_seen_at,
               cu.banned_at, cu.banned_reason,
               (SELECT COUNT(*) FROM violations v WHERE v.customer_id = cu.id) AS violation_count
        FROM customers cu
        {where}
        ORDER BY cu.first_seen_at DESC, cu.id DESC
        LIMIT ? OFFSET ?
        """,
        [*params, page_size, (page - 1) * page_size],
    ).fetchall()
    return rows, int(total)


# ============== UPDATE: UNBAN (F09, FR-15) ==============

def get_customer_with_violation_count(conn: sqlite3.Connection, customer_id: int) -> Optional[sqlite3.Row]:
    """One customer row in the dashboard shape (same computed columns as the list rows)."""
    return conn.execute(
        """
        SELECT cu.id, cu.external_id, cu.case_status, cu.first_seen_at,
               cu.banned_at, cu.banned_reason,
               (SELECT COUNT(*) FROM violations v WHERE v.customer_id = cu.id) AS violation_count
        FROM customers cu
        WHERE cu.id = ?
        """,
        (customer_id,),
    ).fetchone()


def unban_customer(conn: sqlite3.Connection, *, customer_id: int) -> None:
    """Lifts the ban: case_status back to 'active', banned fields cleared.

    The violations rows stay untouched — they are the audit trail; only the
    status (and with it the FR-15 chat ignore) is lifted. Idempotent by design:
    running it on an already-active customer is a harmless no-op.
    """
    conn.execute(
        """
        UPDATE customers
        SET case_status = 'active', banned_at = NULL, banned_reason = NULL
        WHERE id = ?
        """,
        (customer_id,),
    )


# ============== CREATE ==============

def get_or_create_customer(conn: sqlite3.Connection, *, external_id: str) -> sqlite3.Row:
    """Returns the customer row, creating it with case_status='active' on first contact."""
    row = get_customer_by_external_id(conn, external_id)
    if row is not None:
        return row
    conn.execute(
        "INSERT INTO customers (external_id, case_status) VALUES (?, 'active')",
        (external_id,),
    )
    return get_customer_by_external_id(conn, external_id)


# ============== UPDATE ==============

def set_case_status(
    conn: sqlite3.Connection,
    *,
    customer_id: int,
    status: str,
    banned_reason: Optional[str] = None,
) -> None:
    """Updates case_status. When banning, also stamps banned_at/banned_reason."""
    if status == "banned":
        conn.execute(
            """
            UPDATE customers
            SET case_status = 'banned', banned_at = datetime('now'), banned_reason = ?
            WHERE id = ?
            """,
            (banned_reason, customer_id),
        )
        return
    conn.execute(
        "UPDATE customers SET case_status = ? WHERE id = ?",
        (status, customer_id),
    )
