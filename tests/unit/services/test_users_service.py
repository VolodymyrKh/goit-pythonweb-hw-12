"""Unit tests for UserService edge cases."""

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from src.schemas import UserCreate
from src.services.users import UserService


@pytest.fixture
def service(fake_redis):
    service = UserService(AsyncMock())
    service.repository = AsyncMock()
    return service


async def test_create_user_race_condition_returns_409(service):
    service.repository.get_user_by_username_or_email.return_value = None
    service.repository.create_user.side_effect = IntegrityError("INSERT", {}, Exception())

    with pytest.raises(HTTPException) as exc:
        await service.create_user(
            UserCreate(username="alice", email="alice@example.com", password="secret123")
        )

    assert exc.value.status_code == 409
    service.repository.db.rollback.assert_awaited_once()


async def test_confirm_email_unknown_user_does_nothing(service):
    service.repository.get_user_by_email.return_value = None

    await service.confirm_email("ghost@example.com")

    service.repository.confirm_email.assert_not_awaited()


async def test_update_avatar_unknown_user_returns_none(service):
    service.repository.update_avatar_url.return_value = None

    assert await service.update_avatar_url("ghost@example.com", "url") is None
