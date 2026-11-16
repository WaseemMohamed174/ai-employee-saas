"""Violations service — dashboard list + policy management for the store owner (F08, FR-13/FR-14).

Read-only view over the tenant DB with the same tenant isolation as the
complaints service (platform lookup for the slug, then the tenant DB).
Policy upsert is the one write path; the chat engine reads the same rows.
"""
from __future__ import annotations

import logging

from backend.core.errors import ForbiddenError
from backend.schemas.violations import (
    ViolationListItem,
    ViolationListResponse,
    ViolationPolicyCreate,
    ViolationPolicyItem,
    ViolationPolicyListResponse,
    ViolationPolicyResponse,
)
from backend.shared.store_access import tenant_session_for_store
from database.queries import violations as violations_q

logger = logging.getLogger("shop-assistant.violations")


# ============== VIOLATIONS LIST ==============

def list_violations(
    *,
    store_id: int,
    page: int = 1,
    page_size: int = 20,
    action: str | None = None,
) -> ViolationListResponse:
    """Returns paginated violations for the dashboard table."""
    if store_id <= 0:
        raise ForbiddenError("Store not found.")
    with tenant_session_for_store(store_id) as tconn:
        rows, total = violations_q.get_violations_paginated(
            tconn, page=page, page_size=page_size, action=action,
        )
    return ViolationListResponse(
        items=[_row_to_item(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


def _row_to_item(row) -> ViolationListItem:  # noqa: ANN001 — sqlite3.Row
    return ViolationListItem(
        id=int(row["id"]),
        customer_id=int(row["customer_id"]),
        customer_external_id=str(row["customer_external_id"]),
        action=str(row["action"]),
        reason=row["reason"],
        created_at=str(row["created_at"]),
        expires_at=row["expires_at"],
    )


# ============== POLICIES (FR-14) ==============

def list_policies(*, store_id: int) -> ViolationPolicyListResponse:
    """Returns all configured policies in escalation order."""
    with tenant_session_for_store(store_id) as tconn:
        rows = violations_q.list_policies(tconn)
    return ViolationPolicyListResponse(items=[_policy_row_to_item(row) for row in rows])


def save_policy(*, store_id: int, payload: ViolationPolicyCreate) -> ViolationPolicyResponse:
    """Creates or updates one escalation policy (same action = upsert, FR-14)."""
    with tenant_session_for_store(store_id) as tconn:
        existing = violations_q.get_policy_by_action(tconn, payload.action)
        if existing is None:
            violations_q.create_policy(
                tconn,
                action=payload.action,
                threshold_count=payload.threshold_count,
                threshold_window_hours=payload.threshold_window_hours,
                auto_apply=payload.auto_apply,
            )
        else:
            violations_q.update_policy(
                tconn,
                policy_id=int(existing["id"]),
                threshold_count=payload.threshold_count,
                threshold_window_hours=payload.threshold_window_hours,
                auto_apply=payload.auto_apply,
            )
        row = violations_q.get_policy_by_action(tconn, payload.action)
        assert row is not None, "policy row vanished inside its own transaction"
    logger.info("store %s saved violation policy %s (threshold %d/%dh, auto_apply=%s)",
                store_id, payload.action, payload.threshold_count,
                payload.threshold_window_hours, payload.auto_apply)
    return ViolationPolicyResponse(policy=_policy_row_to_item(row))


def _policy_row_to_item(row) -> ViolationPolicyItem:  # noqa: ANN001 — sqlite3.Row
    return ViolationPolicyItem(
        id=int(row["id"]),
        action=str(row["action"]),
        threshold_count=int(row["threshold_count"]),
        threshold_window_hours=int(row["threshold_window_hours"]),
        auto_apply=bool(row["auto_apply"]),
        created_at=str(row["created_at"]),
    )
