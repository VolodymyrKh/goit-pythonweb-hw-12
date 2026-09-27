"""Unit tests for sending emails."""

from unittest.mock import AsyncMock, patch

from fastapi_mail.errors import ConnectionErrors

from src.services import email as email_service
from src.services.auth import get_email_from_token


async def test_send_verification_email():
    with patch.object(email_service.FastMail, "send_message", new=AsyncMock()) as send:
        await email_service.send_verification_email("alice@example.com", "alice", "http://host/")

    message = send.call_args.args[0]
    assert send.call_args.kwargs["template_name"] == "verify_email.html"
    assert message.subject == "Confirm your email"
    assert message.recipients[0].email == "alice@example.com"
    assert message.template_body["username"] == "alice"
    assert get_email_from_token(message.template_body["token"]) == "alice@example.com"


async def test_send_password_reset_email():
    with patch.object(email_service.FastMail, "send_message", new=AsyncMock()) as send:
        await email_service.send_password_reset_email(
            "alice@example.com", "alice", "http://host/", "reset-token"
        )

    message = send.call_args.args[0]
    assert send.call_args.kwargs["template_name"] == "reset_password_email.html"
    assert message.subject == "Reset your password"
    assert message.template_body == {
        "host": "http://host/",
        "username": "alice",
        "token": "reset-token",
    }


async def test_smtp_errors_are_logged_not_raised(caplog):
    failing = AsyncMock(side_effect=ConnectionErrors("SMTP is down"))
    with patch.object(email_service.FastMail, "send_message", new=failing):
        await email_service.send_verification_email("alice@example.com", "alice", "http://host/")

    assert "Failed to send" in caplog.text


def test_email_templates_render_links():
    env = email_service.FastMail(email_service.conf).config.template_engine()
    verify = env.get_template("verify_email.html").render(
        host="http://host/", username="alice", token="abc"
    )
    reset = env.get_template("reset_password_email.html").render(
        host="http://host/", username="alice", token="xyz"
    )

    assert "http://host/api/auth/confirmed_email/abc" in verify
    assert "http://host/api/auth/reset_password/xyz" in reset
