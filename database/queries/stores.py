"""Store queries — reads/writes on the `stores` table.

Each user has at most one store (enforced at the service layer, not the DB schema,
to allow future multi-store support without migration).
"""
from __future__ import annotations

import sqlite3
from typing import Optional


# ============== CREATE ==============

def create_store(
    conn: sqlite3.Connection,
    *,
    owner_user_id: int,
    slug: str,
    name: str,
) -> int:
    """Inserts a new store. Raises sqlite3.IntegrityError if slug is taken."""
    cur = conn.execute(
        """
        INSERT INTO stores (owner_user_id, slug, name)
        VALUES (?, ?, ?)
        """,
        (owner_user_id, slug.lower(), name),
    )
    return int(cur.lastrowid)


# ============== READ ==============

def get_store_by_slug(conn: sqlite3.Connection, slug: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM stores WHERE slug = ?",
        (slug.lower(),),
    ).fetchone()


def get_store_by_id(conn: sqlite3.Connection, store_id: int) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM stores WHERE id = ?",
        (store_id,),
    ).fetchone()


def get_store_by_owner(conn: sqlite3.Connection, owner_user_id: int) -> Optional[sqlite3.Row]:
    """Returns the store owned by the given user, or None."""
    return conn.execute(
        "SELECT * FROM stores WHERE owner_user_id = ? ORDER BY id ASC LIMIT 1",
        (owner_user_id,),
    ).fetchone()


# ============== UPDATE ==============

def update_default_persona(
    conn: sqlite3.Connection,
    store_id: int,
    persona_id: int,
) -> bool:
    cur = conn.execute(
        "UPDATE stores SET default_persona_id = ? WHERE id = ?",
        (persona_id, store_id),
    )
    return cur.rowcount > 0
