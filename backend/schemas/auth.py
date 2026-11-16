"""Auth schemas — Pydantic validation for all auth endpoints.

Per CODE_RULES 6.2: every input is validated in `schemas/` before the Service.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# ============== REQUEST SCHEMAS ==============

class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(default="", max_length=100)
    # Support round S2: trial signup — the account is created pre-verified so a
    # reviewer can log in and try the project without the email-confirmation step.
    # The normal signup flow is unchanged; this only adds an entry method.
    trial: bool = False


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=10, max_length=200)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    new_password: str = Field(min_length=8, max_length=128)


class GoogleAuthRequest(BaseModel):
    google_id_token: str = Field(min_length=10, max_length=4096)


# ============== RESPONSE SCHEMAS ==============

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    is_email_verified: bool
    is_platform_admin: bool = False
    created_at: str


class SignupResponse(BaseModel):
    user_id: int
    pending_verification: bool = True
    verification_token: Optional[str] = None  # Only present in mock/dev mode (when SMTP is not configured)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class VerifyEmailResponse(BaseModel):
    verified: bool = True
    user_id: int


class ForgotPasswordResponse(BaseModel):
    sent: bool = True
    reset_token: Optional[str] = None  # Only present in mock/dev mode


class ResetPasswordResponse(BaseModel):
    reset: bool = True


class GoogleAuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    created_new_user: bool = False


# ============== MAPPING ==============

def user_to_response(row: dict) -> UserResponse:
    """Maps a user dict (from a sqlite3.Row) to the UserResponse schema."""
    return UserResponse(
        id=int(row["id"]),
        email=str(row["email"]),
        full_name=str(row["full_name"]),
        is_email_verified=bool(row["is_email_verified"]),
        is_platform_admin=bool(row.get("is_platform_admin", 0)),
        created_at=str(row["created_at"]),
    )
