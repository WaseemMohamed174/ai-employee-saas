"""Complaints service — dashboard list for the store owner (F07, FR-13).

A complaint = an assistant message whose analysis has is_complaint = 1.
Read-only view over the tenant DB with the same tenant isolation as the
conversations service (platform lookup for the slug, then the tenant DB).
"""
from __future__ import annotations

import logging

from backend.core.errors import ForbiddenError
from backend.schemas.complaints import ComplaintListItem, ComplaintListResponse
from backend.shared.store_access import tenant_session_for_store
from database.queries import analyses as analyses_q

logger = logging.getLogger("shop-assistant.complaints")

EXCERPT_LENGTH = 160


# ============== LIST ==============

def list_complaints(
    *,
    store_id: int,
    page: int = 1,
    page_size: int = 20,
    sentiment: str | None = None,
) -> ComplaintListResponse:
    """Returns paginated complaints for the dashboard table."""
    if store_id <= 0:
        raise ForbiddenError("Store not found.")
    with tenant_session_for_store(store_id) as tconn:
        rows, total = analyses_q.get_complaints_paginated(
            tconn, page=page, page_size=page_size, sentiment=sentiment,
        )
    return ComplaintListResponse(
        items=[_row_to_item(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


def _row_to_item(row) -> ComplaintListItem:  # noqa: ANN001 — sqlite3.Row
    content = str(row["content"] or "")
    customer_message = row["customer_message"]
    return ComplaintListItem(
        analysis_id=int(row["analysis_id"]),
        message_id=int(row["message_id"]),
        conversation_id=int(row["conversation_id"]),
        customer_external_id=str(row["customer_external_id"]),
        message_excerpt=content[:EXCERPT_LENGTH] + ("…" if len(content) > EXCERPT_LENGTH else ""),
        customer_message=(str(customer_message)[:EXCERPT_LENGTH]
                          + ("…" if customer_message and len(str(customer_message)) > EXCERPT_LENGTH else ""))
        if customer_message else None,
        sentiment=row["sentiment"],
        severity=row["severity"],
        sent_at=str(row["sent_at"]),
    )
