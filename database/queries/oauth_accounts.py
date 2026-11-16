"""OAuth account queries — for Google (and future) social login links.

Stores the link between a platform user and an external provider's user ID.
A single platform user can have multiple providers linked (Google, GitHub, ...).
"""
from __future__ import annotations

import sqlite3
from typing import Optional


# ============== CREATE ==============

def create_oauth_account(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    provider: str,
    provider_user_id: str,
) -> int:
    """Inserts a new OAuth link. Raises IntegrityError if (provider, provider_user_id) already exists."""
    cur = conn.execute(
        """
        INSERT INTO oauth_accounts (user_id, provider, provider_user_id)
        VALUES (?, ?, ?)
        """,
        (user_id, provider, provider_user_id),
    )
    return int(cur.lastrowid)


# ============== READ ==============

def get_oauth_account(
    conn: sqlite3.Connection,
    provider: str,
    provider_user_id: str,
) -> Optional[sqlite3.Row]:
    """Find an OAuth link by provider + provider's user ID."""
    return conn.execute(
        """
        SELECT * FROM oauth_accounts
        WHERE provider = ? AND provider_user_id = ?
        """,
        (provider, provider_user_id),
    ).fetchone()


def get_oauth_accounts_by_user(
    conn: sqlite3.Connection,
    user_id: int,
) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM oauth_accounts WHERE user_id = ? ORDER BY created_at",
        (user_id,),
    ).fetchall()
