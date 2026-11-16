"""API key queries — reads/writes on the `api_keys` table.

Keys are stored as SHA-256 hashes of the plain token. The plain token is returned
to the caller exactly once at creation time and never retrievable again.
"""
from __future__ import annotations

import hashlib
import sqlite3
from typing import Optional


# ============== CREATE ==============

def create_api_key(
    conn: sqlite3.Connection,
    *,
    store_id: int,
    key_hash: str,
    name: str = "default",
) -> int:
    """Inserts a new API key row. Returns the key id."""
    cur = conn.execute(
        """
        INSERT INTO api_keys (store_id, key_hash, name)
        VALUES (?, ?, ?)
        """,
        (store_id, key_hash, name),
    )
    return int(cur.lastrowid)


# ============== READ ==============

def get_api_key_by_hash(conn: sqlite3.Connection, key_hash: str) -> Optional[sqlite3.Row]:
    """Looks up an API key by its hash. Used for authenticating chat/data API requests."""
    return conn.execute(
        """
        SELECT * FROM api_keys
        WHERE key_hash = ? AND revoked_at IS NULL
        """,
        (key_hash,),
    ).fetchone()


def get_api_keys_by_store(conn: sqlite3.Connection, store_id: int) -> list[sqlite3.Row]:
    """Returns all API keys for a store (including revoked ones), newest first."""
    return conn.execute(
        """
        SELECT * FROM api_keys
        WHERE store_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (store_id,),
    ).fetchall()


def get_api_key_by_id(conn: sqlite3.Connection, key_id: int, store_id: int) -> Optional[sqlite3.Row]:
    """Returns a single key, scoped to the given store (security: can't fetch other stores' keys)."""
    return conn.execute(
        "SELECT * FROM api_keys WHERE id = ? AND store_id = ?",
        (key_id, store_id),
    ).fetchone()


def count_active_keys(conn: sqlite3.Connection, store_id: int) -> int:
    """Returns the count of non-revoked API keys for a store."""
    row = conn.execute(
        "SELECT COUNT(*) FROM api_keys WHERE store_id = ? AND revoked_at IS NULL",
        (store_id,),
    ).fetchone()
    return int(row[0]) if row else 0


# ============== UPDATE ==============

def revoke_api_key(conn: sqlite3.Connection, key_id: int, store_id: int) -> bool:
    """Marks an API key as revoked (sets revoked_at). Returns True if a row was updated."""
    cur = conn.execute(
        """
        UPDATE api_keys
        SET revoked_at = datetime('now')
        WHERE id = ? AND store_id = ? AND revoked_at IS NULL
        """,
        (key_id, store_id),
    )
    return cur.rowcount > 0


def touch_last_used(conn: sqlite3.Connection, key_id: int) -> None:
    """Updates the last_used_at timestamp for a key. Called when a key is used for chat/data."""
    conn.execute(
        "UPDATE api_keys SET last_used_at = datetime('now') WHERE id = ?",
        (key_id,),
    )


# ============== HELPERS ==============

def hash_plain_key(plain_key: str) -> str:
    """Returns the SHA-256 hex digest of the plain key. Used for storage and lookup."""
    return hashlib.sha256(plain_key.encode("utf-8")).hexdigest()
