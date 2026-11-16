"""Unified API response shape and global exception handlers.

Per CODE_RULES 6.2: "The unified response shape is always `{ ok, data, error }`."
Errors are handled in one global Exception Handler, not try/except in every Route.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("shop-assistant.errors")


# ============== RESPONSE SHAPE ==============

class ApiResponse:
    """Helper to build the unified `{ ok, data, error }` response payload."""

    @staticmethod
    def ok(data: Any = None) -> dict:
        return {"ok": True, "data": data, "error": None}

    @staticmethod
    def error(code: str, message: str, status: int = 400) -> tuple[dict, int]:
        return {"ok": False, "data": None, "error": {"code": code, "message": message}}, status


# ============== EXCEPTION TYPES ==============

class AppError(Exception):
    """Base application error. Subclasses set `code` and `status`."""

    code: str = "app_error"
    status: int = 400

    def __init__(self, message: str, *, code: Optional[str] = None, status: Optional[int] = None):
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status is not None:
            self.status = status


class NotFoundError(AppError):
    code = "not_found"
    status = 404


class UnauthorizedError(AppError):
    code = "unauthorized"
    status = 401


class ForbiddenError(AppError):
    code = "forbidden"
    status = 403


class ConflictError(AppError):
    code = "conflict"
    status = 409


class ValidationError(AppError):
    code = "validation_error"
    status = 422


class RateLimitError(AppError):
    code = "rate_limit_exceeded"
    status = 429


# ============== GLOBAL HANDLER REGISTRATION ==============

def register_exception_handlers(app: FastAPI) -> None:
    """Registers the global exception handlers on the FastAPI app."""

    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        payload, status = ApiResponse.error(exc.code, exc.message, exc.status)
        return JSONResponse(status_code=status, content=payload)

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        # Don't leak internal details to the client — but the SERVER must keep the
        # evidence. Field lesson (attempt 12, 2026-11-16): one overflow request in the
        # rate-limit burst 500'd on the client's machine and service-api.log had NOTHING
        # — the clean response swallowed the only clue. Log the full traceback every time.
        logger.error("Unhandled exception on %s %s: %r",
                     request.method, request.url.path, exc, exc_info=True)
        payload, status = ApiResponse.error("internal_error", "Internal server error", 500)
        return JSONResponse(status_code=status, content=payload)
