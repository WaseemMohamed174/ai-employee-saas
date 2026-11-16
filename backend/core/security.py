"""Security utilities — password hashing (bcrypt) and JWT tokens.

Per CODE_RULES 6.7: secrets live in .env, never in code. Passwords are hashed with bcrypt.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from backend.core.config import get_settings
from backend.core.errors import UnauthorizedError


# ============== PASSWORD HASHING ==============

# The cost factor comes from settings (BCRYPT_ROUNDS env) so the test suite can lower it
# without touching this module; production keeps the 12 default from config.py.
_pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=get_settings().bcrypt_rounds,
)


def hash_password(password: str) -> str:
    """Returns a bcrypt hash of the password."""
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Returns True if the password matches the stored hash."""
    return _pwd_context.verify(password, password_hash)


# ============== JWT TOKENS ==============

def create_access_token(*, user_id: int, email: str) -> str:
    """Creates a signed JWT with the user_id and email, valid for `jwt_expire_minutes`."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_expire_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Decodes and verifies a JWT. Raises UnauthorizedError if invalid or expired."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise UnauthorizedError(f"Invalid or expired token: {exc}") from exc
    return payload


def extract_bearer_token(authorization_header: Optional[str]) -> str:
    """Extracts the token from an `Authorization: Bearer <token>` header value."""
    if not authorization_header:
        raise UnauthorizedError("Missing Authorization header")
    parts = authorization_header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise UnauthorizedError("Authorization header must be 'Bearer <token>'")
    token = parts[1].strip()
    if not token:
        raise UnauthorizedError("Empty bearer token")
    return token
