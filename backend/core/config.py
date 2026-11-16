"""Application settings — read from environment variables.

Per CODE_RULES 6.2: "Settings come from core/config, which reads environment variables.
Scattered os.environ in the code is forbidden."
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings loaded from environment variables (with .env file support)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ============== CORE ==============
    secret_key: str = Field(default="dev-secret-change-me", description="Signing key for sessions and tokens")
    jwt_algorithm: str = Field(default="HS256")
    jwt_expire_minutes: int = Field(default=10080)  # 7 days
    # bcrypt cost factor. 12 = production default; the TEST SUITE passes BCRYPT_ROUNDS=4
    # (Launcher -e) so its many signup/login round-trips don't pay ~0.25s per hash/verify on
    # every case. Hashing behavior (hash→verify, wrong-password rejection) is unchanged.
    bcrypt_rounds: int = Field(default=12)

    # ============== DATABASE ==============
    database_url: str = Field(
        default="sqlite:///database/data/platform.db",
        description="Platform DB connection string",
    )

    # ============== AI ==============
    ai_provider: str = Field(
        default="auto",
        description="auto (first key present: gemini → openai → anthropic, else mock) "
                    "| mock | gemini | openai | anthropic",
    )
    gemini_api_key: str = Field(default="")
    openai_api_key: str = Field(default="")
    anthropic_api_key: str = Field(default="")

    # ============== CORS / RATE LIMIT ==============
    # Comma-separated allow-list. Defaults to the local dev frontend only; set CORS_ORIGINS
    # explicitly (or "*") in .env when the frontend runs on another origin.
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        description="Comma-separated list of allowed CORS origins",
    )
    rate_limit_per_minute: int = Field(default=60)

    # ============== EMAIL (SMTP) ==============
    smtp_host: str = Field(default="")
    smtp_port: int = Field(default=587)
    smtp_user: str = Field(default="")
    smtp_password: str = Field(default="")
    smtp_from_email: str = Field(default="noreply@shop-assistant.local")

    # ============== GOOGLE OAUTH ==============
    google_oauth_client_id: str = Field(default="")
    google_oauth_client_secret: str = Field(default="")

    # ============== FRONTEND (prod) ==============
    # When frontend/dist exists (the prod profile builds it), the API serves the built SPA
    # so one process hosts the whole app. Dev always proxies through Vite on :5173 instead.
    serve_frontend: bool = Field(
        default=True,
        description="Serve frontend/dist as the SPA when the folder exists (prod profile)",
    )

    # ============== STRIPE ==============
    stripe_secret_key: str = Field(default="")
    stripe_webhook_secret: str = Field(default="")

    @property
    def cors_origin_list(self) -> List[str]:
        if self.cors_origins == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
