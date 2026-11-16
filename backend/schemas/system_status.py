"""System status schemas — Pydantic models for the dashboard System Status page (F12, FR-13).

Contract 8.4:
- GET /api/v1/dashboard/system-status → {overall, operational_count, degraded_count,
  version, uptime_seconds, generated_at, services: [...]}
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


# ============== RESPONSE SCHEMAS ==============

class ServiceStatusResponse(BaseModel):
    """One platform service as the owner sees it on the System Status page.

    `status` is one of the two SERVICE_STATUS_* values: `operational` (fully working)
    or `degraded` (working in a safe fallback mode — e.g. the AI adapter answering
    from the mock because no provider key is configured). `uptime_seconds` is only
    meaningful for process-backed services (the API itself) and stays None elsewhere.
    """
    id: str
    name: str
    status: str
    detail: str
    uptime_seconds: Optional[int] = None


class SystemStatusResponse(BaseModel):
    """The whole System Status page in one response (contract 8.4).

    `overall` mirrors the per-service rows (`operational` only when every service is
    operational), so the UI banner can never disagree with the list below it.
    """
    overall: str
    operational_count: int
    degraded_count: int
    version: str
    uptime_seconds: int
    generated_at: str
    services: list[ServiceStatusResponse]
