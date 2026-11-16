"""Customers dashboard routes — the store-owner customers table + unban (F09, contract 8.4).

Dashboard API (JWT auth):
- GET  /api/v1/dashboard/customers                        (?page&page_size&case_status)
- POST /api/v1/dashboard/customers/{customer_id}/unban
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.core.deps import _resolve_store_id, get_current_user
from backend.core.errors import ApiResponse
from backend.services import customers_service

router = APIRouter(prefix="/api/v1", tags=["customers"])


# ============== DASHBOARD API: LIST CUSTOMERS (JWT auth) ==============

@router.get("/dashboard/customers")
def list_customers_dashboard(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    case_status: str | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """List the store's chat customers (paginated, optional case_status filter)."""
    store_id = _resolve_store_id(current_user)
    result = customers_service.list_customers(
        store_id=store_id, page=page, page_size=page_size, case_status=case_status,
    )
    return ApiResponse.ok(result.model_dump())


# ============== DASHBOARD API: UNBAN (FR-15) ==============

@router.post("/dashboard/customers/{customer_id}/unban")
def unban_customer(
    customer_id: int,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Lift the ban on one customer (banned → active, banned fields cleared, FR-15)."""
    store_id = _resolve_store_id(current_user)
    result = customers_service.unban_customer(store_id=store_id, customer_id=customer_id)
    return ApiResponse.ok(result.model_dump())
