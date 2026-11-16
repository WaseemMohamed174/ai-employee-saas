"""Customers service — dashboard list + unban for the store owner (F09, FR-13/FR-15).

Read-only view over the tenant DB with the same tenant isolation as the
violations service (platform lookup for the slug, then the tenant DB).
Unban is the one write path: it lifts the FR-15 chat ignore by resetting
case_status to 'active' and clearing the banned fields; the violations
history stays (audit trail).
"""
from __future__ import annotations

import logging

from backend.core.errors import ForbiddenError, NotFoundError
from backend.schemas.customers import (
    CustomerListItem,
    CustomerListResponse,
    CustomerResponse,
)
from backend.shared.store_access import tenant_session_for_store
from database.queries import customers as customers_q

logger = logging.getLogger("shop-assistant.customers")


# ============== CUSTOMERS LIST ==============

def list_customers(
    *,
    store_id: int,
    page: int = 1,
    page_size: int = 20,
    case_status: str | None = None,
) -> CustomerListResponse:
    """Returns paginated chat customers for the dashboard table."""
    if store_id <= 0:
        raise ForbiddenError("Store not found.")
    with tenant_session_for_store(store_id) as tconn:
        rows, total = customers_q.get_customers_paginated(
            tconn, page=page, page_size=page_size, case_status=case_status,
        )
    return CustomerListResponse(
        items=[_row_to_item(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


def _row_to_item(row) -> CustomerListItem:  # noqa: ANN001 — sqlite3.Row
    return CustomerListItem(
        id=int(row["id"]),
        external_id=str(row["external_id"]),
        case_status=str(row["case_status"]),
        first_seen_at=str(row["first_seen_at"]),
        banned_at=row["banned_at"],
        banned_reason=row["banned_reason"],
        violation_count=int(row["violation_count"]),
    )


# ============== UNBAN (FR-15) ==============

def unban_customer(*, store_id: int, customer_id: int) -> CustomerResponse:
    """Lifts the ban on one customer (banned → active, banned fields cleared).

    404 when the customer does not belong to this store (or does not exist —
    the tenant DB makes both the same). Idempotent: unbanning an already-active
    customer is a no-op that returns the current state.
    """
    if store_id <= 0:
        raise ForbiddenError("Store not found.")
    with tenant_session_for_store(store_id) as tconn:
        row = customers_q.get_customer_with_violation_count(tconn, customer_id)
        if row is None:
            raise NotFoundError("Customer not found.")
        customers_q.unban_customer(tconn, customer_id=customer_id)
        fresh = customers_q.get_customer_with_violation_count(tconn, customer_id)
        assert fresh is not None, "customer row vanished inside its own transaction"
    logger.info("store %s unbanned customer %s (case_status=%s)",
                store_id, customer_id, str(fresh["case_status"]))
    return CustomerResponse(customer=_row_to_item(fresh))
