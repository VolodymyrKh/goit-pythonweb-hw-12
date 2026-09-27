"""Unit tests for UserRepository with a mocked database session."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Role, User
from src.repository.users import UserRepository
from src.schemas import UserCreate


@pytest.fixture
def mock_session():
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def repository(mock_session):
    return UserRepository(mock_session)


@pytest.fixture
def user():
    return User(
        id=1,
        username="alice",
        email="alice@example.com",
        hashed_password="old-hash",
        confirmed=False,
        role=Role.USER,
        refresh_token_hash="token-hash",
    )


def mock_result(mock_session, *, one=None, first=None):
    result = MagicMock()
    result.scalar_one_or_none.return_value = one
    result.scalars.return_value.first.return_value = first
    mock_session.execute = AsyncMock(return_value=result)


async def test_get_user_by_id(repository, mock_session, user):
    mock_session.get.return_value = user

    assert await repository.get_user_by_id(1) is user
    mock_session.get.assert_awaited_once_with(User, 1)


async def test_get_user_by_username(repository, mock_session, user):
    mock_result(mock_session, one=user)

    assert await repository.get_user_by_username("alice") is user


async def test_get_user_by_email(repository, mock_session, user):
    mock_result(mock_session, one=user)

    assert await repository.get_user_by_email("alice@example.com") is user


async def test_get_user_by_username_or_email(repository, mock_session, user):
    mock_result(mock_session, first=user)

    assert await repository.get_user_by_username_or_email("alice", "x@example.com") is user


async def test_create_user(repository, mock_session):
    body = UserCreate(username="bob", email="bob@example.com", password="secret123")

    result = await repository.create_user(body, "hashed", "https://avatar")

    assert result.username == "bob"
    assert result.hashed_password == "hashed"
    assert result.avatar == "https://avatar"
    mock_session.add.assert_called_once_with(result)
    mock_session.commit.assert_awaited_once()
    mock_session.refresh.assert_awaited_once_with(result)


async def test_confirm_email(repository, mock_session, user):
    mock_result(mock_session, one=user)

    await repository.confirm_email(user.email)

    assert user.confirmed is True
    mock_session.commit.assert_awaited_once()


async def test_confirm_email_unknown_user(repository, mock_session):
    mock_result(mock_session, one=None)

    await repository.confirm_email("ghost@example.com")

    mock_session.commit.assert_not_awaited()


async def test_update_avatar_url(repository, mock_session, user):
    mock_result(mock_session, one=user)

    result = await repository.update_avatar_url(user.email, "https://new-avatar")

    assert result is user
    assert user.avatar == "https://new-avatar"
    mock_session.commit.assert_awaited_once()


async def test_update_avatar_url_unknown_user(repository, mock_session):
    mock_result(mock_session, one=None)

    assert await repository.update_avatar_url("ghost@example.com", "url") is None


async def test_update_password_revokes_refresh_token(repository, mock_session, user):
    result = await repository.update_password(user, "new-hash")

    assert result is user
    assert user.hashed_password == "new-hash"
    assert user.refresh_token_hash is None
    mock_session.commit.assert_awaited_once()


async def test_update_refresh_token(repository, mock_session, user):
    await repository.update_refresh_token(user, "new-token-hash")

    assert user.refresh_token_hash == "new-token-hash"
    mock_session.commit.assert_awaited_once()


async def test_update_role(repository, mock_session, user):
    mock_session.get.return_value = user

    result = await repository.update_role(1, Role.ADMIN)

    assert result is user
    assert user.role == Role.ADMIN
    mock_session.commit.assert_awaited_once()


async def test_update_role_unknown_user(repository, mock_session):
    mock_session.get.return_value = None

    assert await repository.update_role(99, Role.ADMIN) is None
    mock_session.commit.assert_not_awaited()
