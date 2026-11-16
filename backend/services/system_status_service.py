"""System status service — the dashboard System Status page (F12, FR-13).

Read-only health report of the platform services the owner's AI employee runs on:
the REST API process (with its live uptime), the SQLite databases (platform + this
store's tenant file), the configured AI provider, and the email delivery mode.

Design decisions (F12 Plan):
- NO external calls and NO synthetic data: every row is derived from live process
  and configuration state, so the page is honest by construction (a degraded row
  means the feature that depends on it really is running in a fallback mode).
- `overall` is `operational` only when every service is operational — the UI banner
  and the service list can never disagree because both come from this one response.
- Provider keys are NEVER echoed: rows carry the provider name / mode, not secrets.
- `PROCESS_STARTED_AT` is captured at module import (uvicorn imports the app once
  per worker), so `uptime_seconds` counts the API process's real lifetime.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from backend.core.config import get_settings
from backend.core.errors import ForbiddenError
from backend.schemas.system_status import ServiceStatusResponse, SystemStatusResponse
from backend.services.ai.adapter import get_adapter
from backend.shared.constants import (
    AI_PROVIDER_MOCK,
    APP_NAME,
    APP_VERSION,
    SERVICE_STATUS_DEGRADED,
    SERVICE_STATUS_OPERATIONAL,
)
from database.connection import platform_session, tenant_db_path
from database.queries import stores as stores_q

logger = logging.getLogger("shop-assistant.status")

# Captured when this module is first imported by the API process (≈ server start).
PROCESS_STARTED_AT: float = time.monotonic()


def _human_size(num_bytes: int) -> str:
    """Renders a file size the way the page shows it (B / KB / MB)."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes / (1024 * 1024):.1f} MB"


def get_system_status(*, store_id: int) -> SystemStatusResponse:
    """Builds the whole status page payload: 4 service rows + the overall verdict."""
    if store_id <= 0:
        raise ForbiddenError("Store not found.")
    settings = get_settings()
    uptime = max(0, int(time.monotonic() - PROCESS_STARTED_AT))
    services: list[ServiceStatusResponse] = []

    # ---- 1. REST API: the process serving this very request. ----
    services.append(ServiceStatusResponse(
        id="api",
        name="REST API",
        status=SERVICE_STATUS_OPERATIONAL,
        detail=f"{APP_NAME} v{APP_VERSION} — serving /api/v1 (this request answered in-process)",
        uptime_seconds=uptime,
    ))

    # ---- 2. Database: platform.db (we just queried it for the JWT) + this store's tenant file. ----
    db_detail = "platform.db reachable"
    with platform_session() as conn:
        store = stores_q.get_store_by_id(conn, store_id)
        if store is None:
            raise ForbiddenError("Store not found.")
        slug = str(store["slug"])
        tenant_path: Path = tenant_db_path(slug)
        if tenant_path.exists():
            db_detail += f" + tenant_{slug}.db ({_human_size(tenant_path.stat().st_size)})"
        else:  # the tenant file is created on first store data — missing is still operational
            db_detail += f" + tenant_{slug}.db (created on first use)"
    services.append(ServiceStatusResponse(
        id="database",
        name="Database",
        status=SERVICE_STATUS_OPERATIONAL,
        detail=db_detail,
    ))

    # ---- 3. AI provider: the adapter's own selection — the exact provider chats use. ----
    provider = get_adapter().select_provider()
    if provider == AI_PROVIDER_MOCK:
        ai_status, ai_detail = SERVICE_STATUS_DEGRADED, (
            "mock — canned answers because no provider key is configured "
            "(set GEMINI_API_KEY in .env to go live)"
        )
    else:
        ai_status = SERVICE_STATUS_OPERATIONAL
        ai_detail = f"{provider} — API key configured"
    services.append(ServiceStatusResponse(
        id="ai_provider",
        name="AI Provider",
        status=ai_status,
        detail=ai_detail,
    ))

    # ---- 4. Email delivery: real SMTP or the safe mock mode. ----
    if settings.smtp_host:
        email_status, email_detail = SERVICE_STATUS_OPERATIONAL, f"SMTP via {settings.smtp_host}"
    else:
        email_status, email_detail = SERVICE_STATUS_DEGRADED, (
            "mock mode — verification and reset links are returned to the client instead of "
            "emailed (set SMTP_HOST to enable real delivery)"
        )
    services.append(ServiceStatusResponse(
        id="email",
        name="Email delivery",
        status=email_status,
        detail=email_detail,
    ))

    degraded = sum(1 for s in services if s.status == SERVICE_STATUS_DEGRADED)
    operational = len(services) - degraded
    overall = SERVICE_STATUS_OPERATIONAL if degraded == 0 else SERVICE_STATUS_DEGRADED
    logger.info("status report: overall=%s (%d operational / %d degraded)", overall, operational, degraded)
    return SystemStatusResponse(
        overall=overall,
        operational_count=operational,
        degraded_count=degraded,
        version=APP_VERSION,
        uptime_seconds=uptime,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        services=services,
    )
