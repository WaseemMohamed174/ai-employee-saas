"""FastAPI entry point for AI Employee (shop-assistant).

Exposes `app` for uvicorn: `uvicorn main:app --reload`.

Per CODE_RULES 6.2:
- One Route = one job, with no business logic inside it.
- Every input is validated in `schemas/` before the Service.
- The unified response shape is `{ ok, data, error }`.
- Errors are handled in one global Exception Handler.
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api.routes import api_keys as api_keys_routes
from backend.api.routes import alerts as alerts_routes
from backend.api.routes import auth as auth_routes
from backend.api.routes import chat as chat_routes
from backend.api.routes import complaints as complaints_routes
from backend.api.routes import conversations as conversations_routes
from backend.api.routes import data as data_routes
from backend.api.routes import health as health_routes
from backend.api.routes import plans as plans_routes
from backend.api.routes import stores as stores_routes
from backend.api.routes import violations as violations_routes
from backend.api.routes import customers as customers_routes
from backend.api.routes import persona as persona_routes
from backend.api.routes import system_status as system_status_routes
from backend.api.routes import subscriptions as subscriptions_routes
from backend.api.routes import overview as overview_routes
from backend.core.config import get_settings
from backend.core.errors import register_exception_handlers
from backend.shared.constants import APP_NAME, APP_VERSION

# ============== LOGGING ==============

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("shop-assistant")


# ============== APP FACTORY ==============

def create_app() -> FastAPI:
    """Application factory. Builds and configures the FastAPI app."""
    settings = get_settings()

    app = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
        description="AI assistant SaaS for e-commerce stores.",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # ============== MIDDLEWARE ==============
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ============== EXCEPTION HANDLERS ==============
    register_exception_handlers(app)

    # ============== ROUTES ==============
    app.include_router(health_routes.router)
    app.include_router(auth_routes.router)
    app.include_router(plans_routes.router)
    app.include_router(stores_routes.router)
    app.include_router(api_keys_routes.router)
    app.include_router(data_routes.router)
    app.include_router(chat_routes.router)
    app.include_router(conversations_routes.router)
    app.include_router(complaints_routes.router)
    app.include_router(violations_routes.router)
    app.include_router(customers_routes.router)
    app.include_router(alerts_routes.router)
    app.include_router(persona_routes.router)
    app.include_router(system_status_routes.router)
    app.include_router(subscriptions_routes.router)
    app.include_router(overview_routes.router)

    _mount_frontend_spa(app, settings)

    logger.info("App created: %s v%s", APP_NAME, APP_VERSION)
    return app


def _mount_frontend_spa(app: FastAPI, settings: "Settings") -> None:
    """Serves the built frontend (frontend/dist) when it exists — the prod profile.

    Registered LAST so every real route above (API, /docs, /openapi.json) keeps
    precedence. Deep links (/dashboard/plans, /login, …) fall back to index.html
    so the SPA router takes over; unknown /api/* paths still answer JSON 404s,
    never the HTML shell.
    """
    if not settings.serve_frontend:
        return
    dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    index_file = dist / "index.html"
    if not index_file.is_file():
        logger.info("No frontend/dist build found — SPA serving disabled (dev uses the Vite server)")
        return

    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str) -> FileResponse:
        # Never swallow API/documentation misses: they must stay JSON 404s.
        first = full_path.split("/", 1)[0].lower()
        if first in {"api", "docs", "redoc", "openapi.json"}:
            raise HTTPException(status_code=404, detail="Not found")
        # Serve real files (favicon.ico, images, …) safely — no path traversal.
        if full_path:
            candidate = (dist / full_path).resolve()
            if candidate.is_file() and str(candidate).startswith(str(dist.resolve())):
                return FileResponse(str(candidate))
        return FileResponse(str(index_file))

    logger.info("Serving the built SPA from %s", dist)


app = create_app()
