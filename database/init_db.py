"""Database initializer for AI Employee (shop-assistant).

Run via: python init_db.py
- Creates data/ folder if missing.
- Initializes platform.db with all tables from schema.py.
- Idempotent: safe to re-run; uses CREATE TABLE IF NOT EXISTS.
- Does NOT seed operational data (no default admin). Catalogs are seeded here from their seed scripts (F02 for plans, F11 for personas).

A custom DATABASE_URL (e.g. sqlite:///database/data/test.db) makes this script initialize that DB instead.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# ============== BOOTSTRAP ==============

# Make `database.*` importable when run as a script from the database/ folder.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.connection import ensure_data_dir, platform_db_path  # noqa: E402
from database.schema import get_platform_ddl, get_tenant_ddl  # noqa: E402


def init_platform() -> list[str]:
    """Creates platform.db and all its tables. Returns the list of created table statements."""
    ensure_data_dir()
    path = platform_db_path()
    import sqlite3
    conn = sqlite3.connect(str(path))
    try:
        for stmt in get_platform_ddl():
            conn.execute(stmt)
        conn.commit()
    finally:
        conn.close()
    return get_platform_ddl()


def main() -> int:
    db_url = os.environ.get("DATABASE_URL", "")
    print(f"[init_db] DATABASE_URL = {db_url!r}")
    path = platform_db_path()
    print(f"[init_db] platform.db path = {path}")
    ensure_data_dir()
    stmts = init_platform()
    print(f"[init_db] platform.db initialized with {len(stmts)} statements (CREATE TABLE IF NOT EXISTS).")
    # Show that tenant schema is also defined (for reference).
    tenant_stmts = get_tenant_ddl()
    print(f"[init_db] tenant schema available with {len(tenant_stmts)} statements (used when first tenant DB is created).")
    # Seed the plans catalog (idempotent — uses INSERT ... ON CONFLICT DO UPDATE).
    from database.seed_plans import seed_plans
    plan_count = seed_plans()
    print(f"[init_db] plans catalog seeded: {plan_count} plans (free_trial, starter, pro, business).")
    # Seed the personas catalog (FR-16, idempotent — same upsert pattern as plans).
    from database.seed_personas import seed_personas
    persona_count = seed_personas()
    print(f"[init_db] personas catalog seeded: {persona_count} personas (friendly, professional, concise, detailed).")
    print("[init_db] Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
