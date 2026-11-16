"""Persona queries — reads/writes on the platform `personas` catalog table.

The catalog is a small lookup (4 rows, FR-16) seeded once by seed_personas.py;
`stores.default_persona_id` on the platform DB points at one of its rows.
"""
from __future__ import annotations

import sqlite3
from typing import Optional


# ============== CREATE / UPDATE (seeding) ==============

def upsert_persona(
    conn: sqlite3.Connection,
    *,
    code: str,
    name: str,
    description: str,
    system_prompt_template: str,
) -> int:
    """Inserts or updates one persona by its unique code. Returns its row id."""
    conn.execute(
        """
        INSERT INTO personas (code, name, description, system_prompt_template)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(code) DO UPDATE SET
            name = excluded.name,
            description = excluded.description,
            system_prompt_template = excluded.system_prompt_template
        """,
        (code, name, description, system_prompt_template),
    )
    row = conn.execute("SELECT id FROM personas WHERE code = ?", (code,)).fetchone()
    return int(row[0])


# ============== READ ==============

def list_personas(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """All personas in catalog order (insertion order = the seed order)."""
    return conn.execute(
        "SELECT * FROM personas ORDER BY id ASC",
    ).fetchall()


def get_persona_by_id(conn: sqlite3.Connection, persona_id: int) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM personas WHERE id = ?",
        (persona_id,),
    ).fetchone()


def get_persona_by_code(conn: sqlite3.Connection, code: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM personas WHERE code = ?",
        (code,),
    ).fetchone()
