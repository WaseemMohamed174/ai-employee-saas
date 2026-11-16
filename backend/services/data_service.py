"""Data service — business logic for uploading and listing store data.

Two entry points:
- upload_data (used by both API and dashboard routes)
- list_data (used by the dashboard)

Enforces the plan's data_limit_kb: if current data + new data exceeds the limit, raises 402.
"""
from __future__ import annotations

import logging

from backend.core.errors import ForbiddenError
from backend.schemas.data import (
    DataListResponse,
    UploadResponse,
    data_item_to_response,
)
from database.connection import platform_session, tenant_session
from database.queries import (
    data_upload_log as log_q,
    store_data as data_q,
    stores as stores_q,
    subscriptions as subs_q,
)

logger = logging.getLogger("shop-assistant.data")


# ============== UPLOAD DATA ==============

def upload_data(
    *,
    store_id: int,
    items: list[dict],
    source: str = "api",
    uploaded_by_user_id: int | None = None,
) -> UploadResponse:
    """Inserts items into the store's tenant DB + logs the upload.

    Each item dict must have `id` (the store's item id) and `content`.
    Raises ForbiddenError (402) if the upload would exceed the plan's data limit.
    """
    # Compute the new upload size.
    new_bytes = sum(len(str(item["content"]).encode("utf-8")) for item in items)

    # Resolve store slug + plan limit from platform.db.
    with platform_session() as conn:
        store = stores_q.get_store_by_id(conn, store_id)
        if store is None:
            raise ForbiddenError("Store not found.")
        sub = subs_q.get_active_subscription(conn, store_id)
    if sub is None:
        raise ForbiddenError("No active subscription found for this store.")

    data_limit_kb = int(sub["data_limit_kb"])
    slug = str(store["slug"])

    # Check plan limit.
    with tenant_session(slug) as tconn:
        current_bytes = data_q.get_total_bytes(tconn)
        current_kb = current_bytes // 1024
        new_kb = new_bytes // 1024
        if current_kb + new_kb > data_limit_kb:
            raise ForbiddenError(
                f"Upload would exceed your plan's data limit "
                f"({current_kb} KB used + {new_kb} KB new = {current_kb + new_kb} KB > {data_limit_kb} KB limit). "
                f"Upgrade your plan to upload more data."
            )

        # Create the upload log first (so we can link items to it).
        log_id = log_q.create_log(
            tconn,
            source=source,
            item_count=len(items),
            file_size_bytes=new_bytes,
            uploaded_by_user_id=uploaded_by_user_id,
        )

        # Insert items.
        prepared = [{"item_id": str(item["id"]), "content": str(item["content"])} for item in items]
        data_q.create_items(
            tconn,
            items=prepared,
            source=source,
            upload_log_id=log_id,
        )

    logger.info(
        "Data uploaded: store=%s items=%d bytes=%d log=%d source=%s",
        store_id, len(items), new_bytes, log_id, source,
    )
    return UploadResponse(
        uploaded_count=len(items),
        total_bytes=new_bytes,
        upload_log_id=log_id,
    )


# ============== LIST DATA ==============

def list_data(*, store_id: int, page: int = 1, page_size: int = 20) -> DataListResponse:
    """Returns paginated store_data items for the dashboard."""
    with platform_session() as conn:
        store = stores_q.get_store_by_id(conn, store_id)
    if store is None:
        raise ForbiddenError("Store not found.")
    slug = str(store["slug"])
    with tenant_session(slug) as tconn:
        rows, total = data_q.get_items_paginated(tconn, page=page, page_size=page_size)
    return DataListResponse(
        items=[data_item_to_response(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )
