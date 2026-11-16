"""Store access helper — the platform→tenant bridge shared by the dashboard services.

Every owner-facing service needs the same two steps: resolve the user's store
on the platform DB, then open its tenant DB. Written once here (6.8).
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from backend.core.errors import ForbiddenError
from database.connection import platform_session, tenant_session
from database.queries import stores as stores_q


def resolve_store_slug(store_id: int) -> str:
    """The tenant slug of the owner's store; ForbiddenError when missing."""
    if store_id <= 0:
        raise ForbiddenError("Store not found.")
    with platform_session() as conn:
        store = stores_q.get_store_by_id(conn, store_id)
    if store is None:
        raise ForbiddenError("Store not found.")
    return str(store["slug"])


@contextmanager
def tenant_session_for_store(store_id: int) -> Iterator[sqlite3.Connection]:
    """Opens the store's tenant DB session after the platform lookup."""
    with tenant_session(resolve_store_slug(store_id)) as conn:
        yield conn
