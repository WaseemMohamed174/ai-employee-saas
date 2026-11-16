"""Email service — sends verification and password reset emails.

Two modes:
- **Mock mode** (default): when SMTP_HOST is empty, the verification/reset token is returned to
  the caller (for testing) and the email body is logged. No real email is sent.
- **SMTP mode**: when SMTP_HOST is set, sends a real email via SMTP using the configured credentials.

The mode is determined by the SMTP_HOST setting. The caller does not need to know which mode is active —
the function returns the same shape either way.
"""
from __future__ import annotations

import logging
import re
import smtplib
from email.message import EmailMessage
from typing import Optional

from backend.core.config import get_settings

logger = logging.getLogger("shop-assistant.email")


# ============== PUBLIC API ==============

def send_verification_email(*, to_email: str, token: str) -> Optional[str]:
    """Sends the verify-email link. Returns the token in mock mode (for testing), None in SMTP mode."""
    verify_url = f"/verify-email?token={token}"
    body = (
        f"Welcome to AI Employee!\n\n"
        f"Please verify your email by clicking the link below (or pasting it into your browser):\n"
        f"{verify_url}\n\n"
        f"This link expires in 24 hours.\n"
        f"If you didn't sign up, you can ignore this email.\n"
    )
    return _send_or_mock(
        to_email=to_email,
        subject="Verify your AI Employee account",
        body=body,
        token_to_return_in_mock_mode=token,
    )


def send_reset_email(*, to_email: str, token: str) -> Optional[str]:
    """Sends the password reset link. Returns the token in mock mode (for testing), None in SMTP mode."""
    reset_url = f"/reset-password?token={token}"
    body = (
        f"We received a request to reset your AI Employee password.\n\n"
        f"Reset your password by visiting:\n"
        f"{reset_url}\n\n"
        f"This link expires in 24 hours.\n"
        f"If you didn't request a reset, you can ignore this email.\n"
    )
    return _send_or_mock(
        to_email=to_email,
        subject="Reset your AI Employee password",
        body=body,
        token_to_return_in_mock_mode=token,
    )


# ============== INTERNAL ==============

def _send_or_mock(*, to_email: str, subject: str, body: str, token_to_return_in_mock_mode: str) -> Optional[str]:
    """Sends via SMTP if configured, else logs a self-service link and returns the token (for dev/test)."""
    settings = get_settings()
    if not settings.smtp_host:
        logger.info("[mock-email] to=%s subject=%r body=%s", to_email, subject, body)
        # Support round S1 (2026-11-16, user report "email login doesn't work"):
        # mock mode logged only a RELATIVE link — useless in a terminal, and nothing said
        # that no real email went out. Print the FULL clickable URL (first CORS origin is
        # the app origin) and state plainly that this is mock mode.
        origin = settings.cors_origins.split(",")[0].strip().rstrip("/")
        match = re.search(r"/(?:verify-email|reset-password)\?token=\S+", body)
        if match and origin.startswith("http"):
            logger.info(
                "[mock-email] NO real email was sent (SMTP not configured — mock mode). "
                "Open this link in your browser to complete the flow: %s%s",
                origin, match.group(0),
            )
        logger.info("[mock-email] token returned to caller for testing: %s", token_to_return_in_mock_mode)
        return token_to_return_in_mock_mode
    _send_smtp(to_email=to_email, subject=subject, body=body)
    return None


def _send_smtp(*, to_email: str, subject: str, body: str) -> None:
    """Sends a plain-text email via SMTP. Raises on connection failures (caller should handle)."""
    settings = get_settings()
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from_email
    msg["To"] = to_email
    msg.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
        server.starttls()
        if settings.smtp_user and settings.smtp_password:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)
    logger.info("Email sent to %s subject=%r", to_email, subject)
