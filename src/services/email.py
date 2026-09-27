"""Sending emails (email confirmation and password reset) with fastapi-mail.

The functions are meant to run as FastAPI background tasks, so SMTP errors are
logged instead of being raised to the client.
"""

import logging
from pathlib import Path

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from fastapi_mail.errors import ConnectionErrors
from pydantic import EmailStr

from src.conf.config import settings
from src.services.auth import create_email_token

logger = logging.getLogger(__name__)

conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_FROM_NAME=settings.MAIL_FROM_NAME,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_STARTTLS=settings.MAIL_STARTTLS,
    MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
    USE_CREDENTIALS=settings.MAIL_USE_CREDENTIALS,
    VALIDATE_CERTS=settings.MAIL_VALIDATE_CERTS,
    TEMPLATE_FOLDER=Path(__file__).parent / "templates",
)


async def _send(email: EmailStr, subject: str, template: str, body: dict) -> None:
    try:
        message = MessageSchema(
            subject=subject,
            recipients=[email],
            template_body=body,
            subtype=MessageType.html,
        )
        await FastMail(conf).send_message(message, template_name=template)
    except ConnectionErrors as err:
        logger.error("Failed to send '%s' email to %s: %s", subject, email, err)


async def send_verification_email(email: EmailStr, username: str, host: str) -> None:
    """Send a message with an email confirmation link.

    Args:
        email: Recipient address.
        username: Name used in the greeting.
        host: Base URL of the API, used to build the link.
    """
    await _send(
        email,
        "Confirm your email",
        "verify_email.html",
        {"host": host, "username": username, "token": create_email_token(email)},
    )


async def send_password_reset_email(
    email: EmailStr, username: str, host: str, token: str
) -> None:
    """Send a message with a password reset link.

    Args:
        email: Recipient address.
        username: Name used in the greeting.
        host: Base URL of the API, used to build the link.
        token: Single-use password reset token.
    """
    await _send(
        email,
        "Reset your password",
        "reset_password_email.html",
        {"host": host, "username": username, "token": token},
    )
