"""Seed the PERSONAS catalog with the 4 ready-made assistant themes (FR-16).

This is a named, clear script — the only place where persona catalog data is
defined. The `system_prompt_template` of each row is the exact instruction the
AI adapter injects into the chat system prompt, so the dashboard selection and
the chat behavior can never drift apart. Idempotent: INSERT ... ON CONFLICT
re-running after the first seed is a no-op.

Run via: python seed_personas.py  (or automatically called by init_db.py)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# ============== BOOTSTRAP ==============

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.connection import platform_db_path, ensure_data_dir  # noqa: E402
from database.queries.personas import upsert_persona  # noqa: E402


# ============== PERSONA CATALOG (FR-16 — the 4 ready-made themes) ==============
# The instructions mirror backend/services/ai/prompts.py PERSONA_INSTRUCTIONS:
# the DB row is the dashboard-facing source of truth, prompts.py keeps the
# chat-side fallback for stores that never picked one (default = professional).

PERSONAS = [
    {
        "code": "friendly",
        "name": "Friendly",
        "description": "Warm and casual chat that feels like a helpful friend — light emojis where natural.",
        "system_prompt_template": "You are warm and casual. Use the customer's language and light emojis where natural.",
    },
    {
        "code": "professional",
        "name": "Professional",
        "description": "Polished and formal answers with a helpful, business-like tone. No emojis.",
        "system_prompt_template": "You are polished and formal. No emojis. Keep a helpful, professional tone.",
    },
    {
        "code": "concise",
        "name": "Concise",
        "description": "Short and to the point — at most 2 short sentences unless the customer asks for detail.",
        "system_prompt_template": "Answer in at most 2 short sentences unless the customer asks for detail.",
    },
    {
        "code": "detailed",
        "name": "Detailed",
        "description": "Full explanations with context and concrete examples for customers who want the whole picture.",
        "system_prompt_template": "Give full explanations with context and concrete examples.",
    },
]


# ============== SEED FUNCTION ==============

def seed_personas() -> int:
    """Inserts the 4 personas if they don't exist. Returns the count of personas now in the table."""
    import sqlite3
    ensure_data_dir()
    conn = sqlite3.connect(str(platform_db_path()))
    try:
        for persona in PERSONAS:
            upsert_persona(conn, **persona)
        conn.commit()
        count = conn.execute("SELECT COUNT(*) FROM personas").fetchone()[0]
    finally:
        conn.close()
    return int(count)


def main() -> int:
    db_url = os.environ.get("DATABASE_URL", "")
    print(f"[seed_personas] DATABASE_URL = {db_url!r}")
    count = seed_personas()
    print(f"[seed_personas] {count} personas in the catalog (friendly, professional, concise, detailed).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
