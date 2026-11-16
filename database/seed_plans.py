"""Seed the PLANS table with the 4 plans from PRD section 4.1.

This is a named, clear script — the only place where plan catalog data is defined.
Idempotent: uses INSERT OR IGNORE so re-running after the first seed is a no-op.

Run via: python seed_plans.py  (or automatically called by init_db.py)
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
from database.queries.plans import upsert_plan  # noqa: E402


# ============== PLAN CATALOG (from PRD 4.1) ==============

PLANS = [
    {
        "code": "free_trial",
        "name": "Free Trial",
        "data_limit_kb": 100,
        "token_limit_month": 1_000,
        "conversation_limit_month": 5,
        "price_usd_cents": 0,
        "is_trial": True,
    },
    {
        "code": "starter",
        "name": "Starter",
        "data_limit_kb": 5 * 1024,        # 5 MB
        "token_limit_month": 50_000,
        "conversation_limit_month": 200,
        "price_usd_cents": 1900,           # $19
        "is_trial": False,
    },
    {
        "code": "pro",
        "name": "Pro",
        "data_limit_kb": 25 * 1024,       # 25 MB
        "token_limit_month": 250_000,
        "conversation_limit_month": 1_000,
        "price_usd_cents": 4900,           # $49
        "is_trial": False,
    },
    {
        "code": "business",
        "name": "Business",
        "data_limit_kb": 100 * 1024,      # 100 MB
        "token_limit_month": 1_000_000,
        "conversation_limit_month": 5_000,
        "price_usd_cents": 14900,          # $149
        "is_trial": False,
    },
]


# ============== SEED FUNCTION ==============

def seed_plans() -> int:
    """Inserts the 4 plans if they don't exist. Returns the count of plans now in the table."""
    import sqlite3
    ensure_data_dir()
    conn = sqlite3.connect(str(platform_db_path()))
    try:
        for plan in PLANS:
            upsert_plan(conn, **plan)
        conn.commit()
        count = conn.execute("SELECT COUNT(*) FROM plans").fetchone()[0]
    finally:
        conn.close()
    return int(count)


def main() -> int:
    db_url = os.environ.get("DATABASE_URL", "")
    print(f"[seed_plans] DATABASE_URL = {db_url!r}")
    count = seed_plans()
    print(f"[seed_plans] {count} plans in the catalog (free_trial, starter, pro, business).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
