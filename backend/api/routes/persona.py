"""Persona dashboard routes — the store-owner persona selection (F11, contract 8.4).

Dashboard API (JWT auth):
- GET /api/v1/dashboard/persona                → {current_persona, using_default, options}
- PUT /api/v1/dashboard/persona {persona_id}   → {persona}   (422 unknown id)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.core.deps import _resolve_store_id, get_current_user
from backend.core.errors import ApiResponse
from backend.schemas.persona import PersonaUpdateRequest
from backend.services import persona_service

router = APIRouter(prefix="/api/v1", tags=["persona"])


# ============== DASHBOARD API: PERSONA PAGE (JWT auth) ==============

@router.get("/dashboard/persona")
def get_persona_dashboard(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """The persona page payload: the store's current choice + the 4-option catalog."""
    store_id = _resolve_store_id(current_user)
    result = persona_service.get_persona_page(store_id=store_id)
    return ApiResponse.ok(result.model_dump())


# ============== DASHBOARD API: SELECT PERSONA (FR-16) ==============

@router.put("/dashboard/persona")
def update_persona_dashboard(
    payload: PersonaUpdateRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Persists the picked persona (422 for an id outside the catalog)."""
    store_id = _resolve_store_id(current_user)
    result = persona_service.update_persona(store_id=store_id, persona_id=payload.persona_id)
    return ApiResponse.ok(result.model_dump())
