"""SQLite connection manager for AI Employee (shop-assistant).

Two database types:
- platform.db: shared, single file. Path comes from DATABASE_URL env var.
- tenant_<slug>.db: one file per store, lives in the same data/ folder.

The backend uses these helpers via:
    from database.connection import get_platform_connection, get_tenant_connection
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Iterator
from urllib.parse import urlparse

from database.schema import get_platform_ddl, get_tenant_ddl


# ============== PATH HELPERS ==============

def _parse_database_url(url: str) -> Path:
    """Converts `sqlite:///{path}` to a Path object. Raises ValueError on unsupported schemes."""
    parsed = urlparse(url)
    if parsed.scheme not in ("sqlite", ""):
        raise ValueError(f"Unsupported database scheme: {parsed.scheme!r}. Only 'sqlite' is supported.")
    path = parsed.path or url.removeprefix("sqlite:///")
    return Path(path).expanduser().resolve()


def platform_db_path() -> Path:
    """Returns the absolute path to platform.db, from DATABASE_URL env var."""
    url = os.environ.get("DATABASE_URL", "sqlite:///database/data/platform.db")
    return _parse_database_url(url)


def tenant_db_path(store_slug: str) -> Path:
    """Returns the absolute path to tenant_<slug>.db, in the same folder as platform.db."""
    safe_slug = "".join(c if c.isalnum() or c in "-_" else "_" for c in store_slug.lower())
    return platform_db_path().parent / f"tenant_{safe_slug}.db"


def data_dir() -> Path:
    """Returns the folder that holds platform.db and tenant_*.db files."""
    return platform_db_path().parent


def ensure_data_dir() -> None:
    """Creates the data/ folder if it doesn't exist."""
    data_dir().mkdir(parents=True, exist_ok=True)


# ============== CONNECTION FACTORIES ==============

def _open(path: Path) -> sqlite3.Connection:
    """Opens a SQLite connection with sane defaults: WAL, FK on, row factory.

    timeout=15 (the busy-wait budget): the sqlite3 default is 5s, and on the client's
    loaded machine the rate-limit test's 6-concurrent-writer burst expired it — one
    request died with "database is locked" → 500 (attempt 12 field failure, 2026-11-16).
    15s absorbs transient lock waits; a genuinely stuck writer still fails, and the
    global handler now logs its traceback (see backend/core/errors.py).
    """
    conn = sqlite3.connect(str(path), detect_types=sqlite3.PARSE_DECLTYPES, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def get_platform_connection() -> sqlite3.Connection:
    """Opens platform.db. Initializes the schema if the file is empty/new."""
    ensure_data_dir()
    path = platform_db_path()
    is_new = not path.exists() or path.stat().st_size == 0
    conn = _open(path)
    if is_new:
        for stmt in get_platform_ddl():
            conn.execute(stmt)
        conn.commit()
    return conn


def get_tenant_connection(store_slug: str) -> sqlite3.Connection:
    """Opens tenant_<slug>.db. Initializes the tenant schema if the file is empty/new.

    Safe to call repeatedly: the schema is CREATE TABLE IF NOT EXISTS."""
    ensure_data_dir()
    path = tenant_db_path(store_slug)
    is_new = not path.exists() or path.stat().st_size == 0
    conn = _open(path)
    if is_new:
        for stmt in get_tenant_ddl():
            conn.execute(stmt)
        conn.commit()
    return conn


# ============== CONTEXT MANAGERS (for `with` usage) ==============

class _ConnCtx:
    """Context manager that yields a connection and closes it on exit (with commit on success)."""

    def __init__(self, factory):
        self._factory = factory
        self._conn: sqlite3.Connection | None = None

    def __enter__(self) -> sqlite3.Connection:
        self._conn = self._factory()
        return self._conn

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._conn is None:
            return
        try:
            if exc_type is None:
                self._conn.commit()
            else:
                self._conn.rollback()
        finally:
            self._conn.close()


def platform_session() -> _ConnCtx:
    """`with platform_session() as conn:` — auto commit/rollback + close."""
    return _ConnCtx(get_platform_connection)


def tenant_session(store_slug: str) -> _ConnCtx:
    """`with tenant_session(slug) as conn:` — auto commit/rollback + close."""
    return _ConnCtx(lambda: get_tenant_connection(store_slug))
