"""Auth service — business logic for signup, login, email verification, password reset, Google OAuth.

Per CODE_RULES 6.2: the service validates inputs (via Pydantic in schemas/), calls database/queries,
and returns plain dicts ready to be serialized by the route. No SQL here.
"""
from __future__ import annotations

import logging
import secrets
import sqlite3

from backend.core.config import get_settings
from backend.core.errors import (
    ConflictError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from backend.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from backend.schemas.auth import (
    ForgotPasswordResponse,
    GoogleAuthResponse,
    ResetPasswordResponse,
    SignupResponse,
    TokenResponse,
    UserResponse,
    VerifyEmailResponse,
    user_to_response,
)
from backend.services import email_service
from database.connection import platform_session
from database.queries import (
    email_verifications as verifications_q,
    oauth_accounts as oauth_q,
    users as users_q,
)

logger = logging.getLogger("shop-assistant.auth")


# ============== SIGNUP ==============

def signup(*, email: str, password: str, full_name: str, trial: bool = False) -> SignupResponse:
    """Creates a new user, queues a verification email, returns the user_id.

    In mock mode (no SMTP configured), the verification token is returned so the caller
    can complete the flow programmatically (e.g. tests).

    Support round S2: with trial=True the account is created PRE-VERIFIED and no
    verification email/token is involved at all — an entry method for reviewers who
    just want to try the project ("sign up as a trial"). The normal flow is untouched.
    """
    with platform_session() as conn:
        existing = users_q.get_user_by_email(conn, email)
        if existing is not None:
            raise ConflictError(f"Email already registered: {email}")
        password_hash = hash_password(password)
        try:
            user_id = users_q.create_user(
                conn,
                email=email,
                password_hash=password_hash,
                full_name=full_name,
            )
        except sqlite3.IntegrityError as exc:
            raise ConflictError(f"Email already registered: {email}") from exc
        if trial:
            # Trial account: verified on the spot — no verification row, no email.
            users_q.set_email_verified(conn, user_id, verified=True)
            token = None
        else:
            token = verifications_q.create_verification(
                conn,
                user_id=user_id,
                purpose=verifications_q.PURPOSE_VERIFY_EMAIL,
            )

    if trial:
        logger.info("User signed up (TRIAL — verification skipped): id=%s email=%s", user_id, email)
        return SignupResponse(
            user_id=user_id,
            pending_verification=False,
            verification_token=None,
        )
    returned_token = email_service.send_verification_email(to_email=email, token=token)
    logger.info("User signed up: id=%s email=%s", user_id, email)
    return SignupResponse(
        user_id=user_id,
        pending_verification=True,
        verification_token=returned_token,
    )


# ============== VERIFY EMAIL ==============

def verify_email(*, token: str) -> VerifyEmailResponse:
    """Marks the user's email as verified using the token from the signup email."""
    with platform_session() as conn:
        row = verifications_q.get_verification_by_token(
            conn, token, purpose=verifications_q.PURPOSE_VERIFY_EMAIL
        )
        if row is None:
            raise NotFoundError("Verification token not found")
        if not verifications_q.is_token_valid(row):
            raise UnauthorizedError("Token expired or already used")
        user_id = int(row["user_id"])
        users_q.set_email_verified(conn, user_id, verified=True)
        verifications_q.mark_verification_used(conn, token)
    logger.info("Email verified: user_id=%s", user_id)
    return VerifyEmailResponse(verified=True, user_id=user_id)


# ============== LOGIN ==============

def login(*, email: str, password: str) -> TokenResponse:
    """Validates credentials and returns a JWT access token."""
    with platform_session() as conn:
        user = users_q.get_user_by_email(conn, email)
    if user is None:
        raise UnauthorizedError("Invalid email or password")
    if not verify_password(password, user["password_hash"]):
        raise UnauthorizedError("Invalid email or password")
    return _build_token_response(dict(user))


# ============== FORGOT PASSWORD ==============

def forgot_password(*, email: str) -> ForgotPasswordResponse:
    """Creates a reset token and emails it. Returns `sent: true` always (don't leak if email exists).

    In mock mode, the reset token is returned so the caller can complete the flow programmatically.
    """
    with platform_session() as conn:
        user = users_q.get_user_by_email(conn, email)
        if user is None:
            # Don't leak whether the email exists. Return success without doing anything.
            logger.info("Forgot-password requested for unknown email: %s", email)
            return ForgotPasswordResponse(sent=True, reset_token=None)
        token = verifications_q.create_verification(
            conn,
            user_id=int(user["id"]),
            purpose=verifications_q.PURPOSE_RESET_PASSWORD,
        )

    returned_token = email_service.send_reset_email(to_email=email, token=token)
    logger.info("Password reset email sent: user_id=%s", user["id"])
    return ForgotPasswordResponse(sent=True, reset_token=returned_token)


# ============== RESET PASSWORD ==============

def reset_password(*, token: str, new_password: str) -> ResetPasswordResponse:
    """Resets the user's password using a valid reset token."""
    with platform_session() as conn:
        row = verifications_q.get_verification_by_token(
            conn, token, purpose=verifications_q.PURPOSE_RESET_PASSWORD
        )
        if row is None:
            raise NotFoundError("Reset token not found")
        if not verifications_q.is_token_valid(row):
            raise UnauthorizedError("Token expired or already used")
        user_id = int(row["user_id"])
        new_hash = hash_password(new_password)
        users_q.update_password(conn, user_id, new_hash)
        verifications_q.mark_verification_used(conn, token)
    logger.info("Password reset: user_id=%s", user_id)
    return ResetPasswordResponse(reset=True)


# ============== GOOGLE OAUTH ==============

def google_auth(*, google_id_token: str) -> GoogleAuthResponse:
    """Authenticates via Google OAuth. Uses real Google Tokeninfo when configured, mock otherwise.

    Mock mode: accepts any `google_id_token` that starts with `mock-` and parses a fake
    email + google_user_id from it. Format: `mock-{email}-{google_user_id}`.
    """
    settings = get_settings()
    if settings.google_oauth_client_id:
        google_user_id, email, full_name = _verify_google_id_token_real(google_id_token, settings)
    else:
        google_user_id, email, full_name = _verify_google_id_token_mock(google_id_token)
    return _login_or_create_google_user(
        google_user_id=google_user_id,
        email=email,
        full_name=full_name,
    )


# ============== GET CURRENT USER ==============

def get_current_user_profile(user: dict) -> UserResponse:
    """Returns the current user's profile. `user` is the dict injected by `get_current_user` dep."""
    return user_to_response(user)


# ============== INTERNAL HELPERS ==============

def _build_token_response(user: dict) -> TokenResponse:
    """Builds a TokenResponse from a user dict."""
    access_token = create_access_token(user_id=int(user["id"]), email=str(user["email"]))
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=user_to_response(user),
    )


def _verify_google_id_token_mock(token: str) -> tuple[str, str, str]:
    """Mock Google OAuth: parses `mock-{email}-{google_user_id}` from the token.

    Raises ValidationError if the token doesn't start with `mock-`.
    """
    if not token.startswith("mock-"):
        raise ValidationError(
            "Mock Google OAuth requires a token starting with 'mock-'. "
            "Set GOOGLE_OAUTH_CLIENT_ID to use real Google OAuth."
        )
    rest = token[len("mock-"):]
    parts = rest.rsplit("-", 1)
    if len(parts) != 2 or "@" not in parts[0]:
        raise ValidationError(
            "Mock token format: 'mock-{email}-{google_user_id}'. Example: 'mock-user@example.com-g_12345'."
        )
    email, google_user_id = parts[0], parts[1]
    return google_user_id, email, email.split("@", 1)[0]


def _verify_google_id_token_real(token: str, settings) -> tuple[str, str, str]:
    """Verifies a Google ID token via the tokeninfo API. Returns (google_user_id, email, name).

    Raises UnauthorizedError on any failure. For production, prefer the official `google-auth`
    library which verifies the signature locally. This HTTP call is sufficient for our basic integration.
    """
    import urllib.error
    import urllib.request
    import json as _json

    url = f"https://oauth2.googleapis.com/tokeninfo?id_token={token}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            payload = _json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise UnauthorizedError(f"Google token verification failed: {exc}") from exc
    audience = payload.get("aud")
    if audience != settings.google_oauth_client_id:
        raise UnauthorizedError("Google token audience mismatch")
    google_user_id = payload.get("sub")
    email = payload.get("email")
    if not google_user_id or not email:
        raise UnauthorizedError("Google token missing sub or email")
    if not payload.get("email_verified"):
        raise UnauthorizedError("Google email not verified")
    full_name = payload.get("name") or email.split("@", 1)[0]
    return google_user_id, email, full_name


def _login_or_create_google_user(*, google_user_id: str, email: str, full_name: str) -> GoogleAuthResponse:
    """Finds or creates the user + OAuth link, returns a token response."""
    created_new = False
    with platform_session() as conn:
        oauth_row = oauth_q.get_oauth_account(conn, "google", google_user_id)
        if oauth_row is not None:
            user = users_q.get_user_by_id(conn, int(oauth_row["user_id"]))
            if user is None:
                raise NotFoundError("OAuth link points to a missing user")
            user_dict = dict(user)
        else:
            # No OAuth link yet — check if a user with that email already exists.
            existing = users_q.get_user_by_email(conn, email)
            if existing is not None:
                user_id = int(existing["id"])
            else:
                # Create a new user with a random password (Google users don't use password login).
                random_password = secrets.token_urlsafe(32)
                try:
                    user_id = users_q.create_user(
                        conn,
                        email=email,
                        password_hash=hash_password(random_password),
                        full_name=full_name,
                    )
                except sqlite3.IntegrityError as exc:
                    raise ConflictError(f"Email already registered: {email}") from exc
                # Google emails are already verified by Google.
                users_q.set_email_verified(conn, user_id, verified=True)
                created_new = True
            oauth_q.create_oauth_account(
                conn,
                user_id=user_id,
                provider="google",
                provider_user_id=google_user_id,
            )
            user = users_q.get_user_by_id(conn, user_id)
            if user is None:
                raise NotFoundError("User creation failed")
            user_dict = dict(user)

    access_token = create_access_token(user_id=int(user_dict["id"]), email=str(user_dict["email"]))
    return GoogleAuthResponse(
        access_token=access_token,
        token_type="bearer",
        user=user_to_response(user_dict),
        created_new_user=created_new,
    )
