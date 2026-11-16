"""Auth routes — signup, login, verify-email, forgot/reset password, Google OAuth, me.

Per CODE_RULES 6.2: one route = one job, no business logic inside. Each route validates input
(via Pydantic schemas), calls the service, and returns the unified `{ ok, data, error }` shape.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.core.deps import get_current_user
from backend.core.errors import ApiResponse
from backend.schemas.auth import (
    ForgotPasswordRequest,
    GoogleAuthRequest,
    LoginRequest,
    ResetPasswordRequest,
    SignupRequest,
    VerifyEmailRequest,
)
from backend.services import auth_service

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


# ============== SIGNUP ==============

@router.post("/signup")
def signup(payload: SignupRequest) -> dict:
    """Register a new user with email + password. trial=true skips email verification (S2)."""
    result = auth_service.signup(
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        trial=payload.trial,
    )
    return ApiResponse.ok(result.model_dump())


# ============== VERIFY EMAIL ==============

@router.post("/verify-email")
def verify_email(payload: VerifyEmailRequest) -> dict:
    """Verify a user's email using the token from the signup email."""
    result = auth_service.verify_email(token=payload.token)
    return ApiResponse.ok(result.model_dump())


# ============== LOGIN ==============

@router.post("/login")
def login(payload: LoginRequest) -> dict:
    """Login with email + password. Returns a JWT access token."""
    result = auth_service.login(email=payload.email, password=payload.password)
    return ApiResponse.ok(result.model_dump())


# ============== GOOGLE OAUTH ==============

@router.post("/google")
def google_auth(payload: GoogleAuthRequest) -> dict:
    """Authenticate with a Google ID token. Mock mode accepts tokens starting with 'mock-'."""
    result = auth_service.google_auth(google_id_token=payload.google_id_token)
    return ApiResponse.ok(result.model_dump())


# ============== FORGOT PASSWORD ==============

@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest) -> dict:
    """Request a password reset link. Always returns `sent: true` (no email-exists leak)."""
    result = auth_service.forgot_password(email=payload.email)
    return ApiResponse.ok(result.model_dump())


# ============== RESET PASSWORD ==============

@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest) -> dict:
    """Reset the password using a valid reset token."""
    result = auth_service.reset_password(token=payload.token, new_password=payload.new_password)
    return ApiResponse.ok(result.model_dump())


# ============== ME ==============

@router.get("/me")
def me(current_user: dict = Depends(get_current_user)) -> dict:
    """Return the current authenticated user's profile."""
    result = auth_service.get_current_user_profile(current_user)
    return ApiResponse.ok(result.model_dump())
