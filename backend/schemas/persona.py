"""Persona schemas — Pydantic models for the dashboard persona page (F11, FR-16).

Contract 8.4:
- GET /api/v1/dashboard/persona → {current_persona, options: [...]}
- PUT /api/v1/dashboard/persona {persona_id} → {persona}   (422 unknown id)
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


# ============== REQUEST SCHEMAS ==============

class PersonaUpdateRequest(BaseModel):
    persona_id: int = Field(ge=1, le=10_000)


# ============== RESPONSE SCHEMAS ==============

class PersonaOptionResponse(BaseModel):
    id: int
    code: str
    name: str
    description: str


class PersonaPageResponse(BaseModel):
    """The whole persona page in one response: the picked persona + the full catalog.

    `current_persona` is null while the store still runs the platform default — the
    `using_default` flag says so explicitly. `effective_persona` is the persona the
    chats actually use RIGHT NOW (the choice, or the platform default professional)
    so the UI can highlight the correct card even before any choice is made.
    """
    current_persona: Optional[PersonaOptionResponse] = None
    using_default: bool = True
    effective_persona: Optional[PersonaOptionResponse] = None
    options: list[PersonaOptionResponse]


class PersonaUpdateResponse(BaseModel):
    persona: PersonaOptionResponse


# ============== MAPPING ==============

def persona_to_response(row: Any) -> PersonaOptionResponse:
    """Maps a personas row (dict or sqlite3.Row) to PersonaOptionResponse."""
    return PersonaOptionResponse(
        id=int(row["id"]),
        code=str(row["code"]),
        name=str(row["name"]),
        description=str(row["description"]),
    )
