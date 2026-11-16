"""Persona service — the dashboard persona page + the chat-side persona resolution (F11, FR-16).

Two jobs:
1. Owner-facing: read the persona catalog + the store's current choice, and persist a
   new choice into `stores.default_persona_id` (platform DB, same row the chat reads).
2. Chat-facing: resolve a store row (the dict the API-key auth already carries) to the
   persona code the adapter should use — falling back to the platform default
   (professional) for stores that never picked one, exactly as before F11.
"""
from __future__ import annotations

import logging

from backend.core.errors import ForbiddenError, ValidationError
from backend.schemas.persona import (
    PersonaOptionResponse,
    PersonaPageResponse,
    PersonaUpdateResponse,
    persona_to_response,
)
from backend.services.ai.prompts import DEFAULT_PERSONA_CODE
from database.connection import platform_session
from database.queries import personas as personas_q
from database.queries import stores as stores_q

logger = logging.getLogger("shop-assistant.persona")


# ============== OWNER-FACING: PAGE + UPDATE ==============

def get_persona_page(*, store_id: int) -> PersonaPageResponse:
    """Current persona + the 4-option catalog in one response (contract 8.4)."""
    if store_id <= 0:
        raise ForbiddenError("Store not found.")
    with platform_session() as conn:
        store = stores_q.get_store_by_id(conn, store_id)
        if store is None:
            raise ForbiddenError("Store not found.")
        options = [persona_to_response(row) for row in personas_q.list_personas(conn)]
        persona_id = store["default_persona_id"]
        current = persona_to_response(personas_q.get_persona_by_id(conn, int(persona_id))) \
            if persona_id is not None else None
        # The persona the chats actually use right now: the choice, else the platform
        # default (professional) — the UI highlights it even before any choice is made.
        effective = current
        if effective is None:
            default_row = personas_q.get_persona_by_code(conn, DEFAULT_PERSONA_CODE)
            effective = persona_to_response(default_row) if default_row is not None else None
    return PersonaPageResponse(
        current_persona=current,
        using_default=current is None,
        effective_persona=effective,
        options=options,
    )


def update_persona(*, store_id: int, persona_id: int) -> PersonaUpdateResponse:
    """Persists the owner's persona choice (422 when the id is not in the catalog)."""
    if store_id <= 0:
        raise ForbiddenError("Store not found.")
    with platform_session() as conn:
        persona = personas_q.get_persona_by_id(conn, persona_id)
        if persona is None:
            raise ValidationError("Unknown persona. Pick one of the listed options.")
        stores_q.update_default_persona(conn, store_id, persona_id)
        option = persona_to_response(persona)
    logger.info("store %s persona set to %s (%s)", store_id, option.code, option.name)
    return PersonaUpdateResponse(persona=option)


# ============== CHAT-FACING: RESOLUTION (FR-16) ==============

def resolve_persona_code_for_store(store: dict) -> str:
    """The persona code a chat with this store must use.

    `store` is the dict the API-key auth already resolved (stores row). The choice
    lives in `default_persona_id`; unmapped rows (missing seed) fall back to the
    platform default so a chat can never crash because of a bad catalog row.
    """
    persona_id = store.get("default_persona_id")
    if persona_id is None:
        return DEFAULT_PERSONA_CODE
    with platform_session() as conn:
        persona = personas_q.get_persona_by_id(conn, int(persona_id))
    if persona is None:
        logger.warning("store persona id %s not in catalog — using default", persona_id)
        return DEFAULT_PERSONA_CODE
    return str(persona["code"])
