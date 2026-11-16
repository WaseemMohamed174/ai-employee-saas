"""Data schemas — Pydantic models for data upload and listing."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ============== REQUEST SCHEMAS ==============

class DataItemInput(BaseModel):
    """A single data item to upload. `item_id` is the store's own id (e.g. product SKU)."""
    id: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=100_000)


class DataUploadRequest(BaseModel):
    """Body for POST /api/v1/data and POST /api/v1/dashboard/database/upload."""
    items: list[DataItemInput] = Field(min_length=1, max_length=500)
    source: str = Field(default="api", max_length=20)


# ============== RESPONSE SCHEMAS ==============

class DataItemResponse(BaseModel):
    id: int
    item_id: str
    content_preview: str  # first 120 chars of content
    source: str
    uploaded_at: str


class UploadResponse(BaseModel):
    uploaded_count: int
    total_bytes: int
    upload_log_id: int


class DataListResponse(BaseModel):
    items: list[DataItemResponse]
    total: int
    page: int
    page_size: int


class UploadLogResponse(BaseModel):
    id: int
    source: str
    item_count: int
    file_size_bytes: int
    uploaded_by_user_id: Optional[int] = None
    uploaded_at: str


class UploadLogListResponse(BaseModel):
    logs: list[UploadLogResponse]
    total: int
    page: int
    page_size: int


# ============== MAPPING ==============

def data_item_to_response(row) -> DataItemResponse:
    """Maps a store_data row to DataItemResponse (with content truncated to preview)."""
    content = str(row["content"])
    preview = content[:120] + ("…" if len(content) > 120 else "")
    return DataItemResponse(
        id=int(row["id"]),
        item_id=str(row["item_id"]),
        content_preview=preview,
        source=str(row["source"]),
        uploaded_at=str(row["uploaded_at"]),
    )


def upload_log_to_response(row) -> UploadLogResponse:
    return UploadLogResponse(
        id=int(row["id"]),
        source=str(row["source"]),
        item_count=int(row["item_count"]),
        file_size_bytes=int(row["file_size_bytes"]),
        uploaded_by_user_id=row["uploaded_by_user_id"],
        uploaded_at=str(row["uploaded_at"]),
    )
