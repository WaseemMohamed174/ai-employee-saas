"""User queries — single source for all reads/writes on the `users` table.

Per CODE_RULES 6.3: every query written once. Multi-step writes go inside a transaction
(handled by the caller via `platform_session()` context manager).
"""
from __future__ import annotations

import sqlite3
from typing import Optional


# ============== CREATE ==============

def create_user(
    conn: sqlite3.Connection,
    *,
    email: str,
    password_hash: str,
    full_name: str = "",
) -> int:
    """Inserts a new user. Raises sqlite3.IntegrityError if email is taken."""
    cur = conn.execute(
        """
        INSERT INTO users (email, password_hash, full_name, is_email_verified)
        VALUES (?, ?, ?, 0)
        """,
        (email.lower(), password_hash, full_name),
    )
    return int(cur.lastrowid)


# ============== READ ==============

def get_user_by_email(conn: sqlite3.Connection, email: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM users WHERE email = ?",
        (email.lower(),),
    ).fetchone()


def get_user_by_id(conn: sqlite3.Connection, user_id: int) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()


# ============== UPDATE ==============

def update_password(conn: sqlite3.Connection, user_id: int, new_password_hash: str) -> bool:
    cur = conn.execute(
        """
        UPDATE users
        SET password_hash = ?, updated_at = datetime('now')
        WHERE id = ?
        """,
        (new_password_hash, user_id),
    )
    return cur.rowcount > 0


def set_email_verified(conn: sqlite3.Connection, user_id: int, verified: bool = True) -> bool:
    cur = conn.execute(
        """
        UPDATE users
        SET is_email_verified = ?, updated_at = datetime('now')
        WHERE id = ?
        """,
        (1 if verified else 0, user_id),
    )
    return cur.rowcount > 0


def update_full_name(conn: sqlite3.Connection, user_id: int, full_name: str) -> bool:
    cur = conn.execute(
        """
        UPDATE users
        SET full_name = ?, updated_at = datetime('now')
        WHERE id = ?
        """,
        (full_name, user_id),
    )
    return cur.rowcount > 0
