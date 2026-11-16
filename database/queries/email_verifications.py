"""Email verification & password reset token queries.

Tokens are urlsafe random strings, stored with a purpose ('verify_email' | 'reset_password')
and an expiry. Used tokens get `used_at` set so they can't be replayed.
"""
from __future__ import annotations

import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional


# ============== CONSTANTS ==============

PURPOSE_VERIFY_EMAIL = "verify_email"
PURPOSE_RESET_PASSWORD = "reset_password"

DEFAULT_TTL_HOURS = 24  # tokens live 24h by default


# ============== CREATE ==============

def create_verification(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    purpose: str,
    ttl_hours: int = DEFAULT_TTL_HOURS,
) -> str:
    """Creates a verification token, returns the plain token (only chance to read it)."""
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=ttl_hours)).isoformat(timespec="seconds")
    conn.execute(
        """
        INSERT INTO email_verifications (user_id, token, purpose, expires_at)
        VALUES (?, ?, ?, ?)
        """,
        (user_id, token, purpose, expires_at),
    )
    return token


# ============== READ ==============

def get_verification_by_token(
    conn: sqlite3.Connection,
    token: str,
    purpose: Optional[str] = None,
) -> Optional[sqlite3.Row]:
    """Fetch a token row. Optionally filter by purpose. Does NOT check expiry or used_at."""
    if purpose is None:
        return conn.execute(
            "SELECT * FROM email_verifications WHERE token = ?",
            (token,),
        ).fetchone()
    return conn.execute(
        "SELECT * FROM email_verifications WHERE token = ? AND purpose = ?",
        (token, purpose),
    ).fetchone()


# ============== UPDATE ==============

def mark_verification_used(conn: sqlite3.Connection, token: str) -> bool:
    cur = conn.execute(
        """
        UPDATE email_verifications
        SET used_at = datetime('now')
        WHERE token = ? AND used_at IS NULL
        """,
        (token,),
    )
    return cur.rowcount > 0


# ============== HELPERS ==============

def is_token_valid(row: sqlite3.Row) -> bool:
    """Returns True if the token row is not used and not expired."""
    if row is None:
        return False
    if row["used_at"] is not None:
        return False
    expires_at = datetime.fromisoformat(row["expires_at"])
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at > datetime.now(timezone.utc)
