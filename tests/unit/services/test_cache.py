"""Unit tests for the Redis user cache."""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from src.database.models import Role, User
from src.services import cache


@pytest.fixture
def user():
    return User(
        id=1,
        username="alice",
        email="alice@example.com",
        hashed_password="secret-hash",
        refresh_token_hash="refresh-hash",
        avatar="https://avatar",
        confirmed=True,
        role=Role.ADMIN,
        created_at=datetime(2026, 9, 27, 12, 0),
    )


@pytest.fixture
def broken_redis(monkeypatch):
    client = AsyncMock()
    client.get.side_effect = RedisConnectionError("down")
    client.set.side_effect = RedisConnectionError("down")
    client.delete.side_effect = RedisConnectionError("down")
    monkeypatch.setattr(cache, "redis_client", client)
    return client


async def test_cache_round_trip(fake_redis, user):
    await cache.cache_user(user)

    restored = await cache.get_cached_user("alice")

    assert restored.id == 1
    assert restored.email == "alice@example.com"
    assert restored.role == Role.ADMIN
    assert restored.created_at == datetime(2026, 9, 27, 12, 0)
    assert restored.hashed_password is None
    assert restored.refresh_token_hash is None


async def test_cache_miss_returns_none(fake_redis):
    assert await cache.get_cached_user("nobody") is None


async def test_invalidate_user(fake_redis, user):
    await cache.cache_user(user)

    await cache.invalidate_user("alice")

    assert await cache.get_cached_user("alice") is None


async def test_user_without_created_at(fake_redis, user):
    user.created_at = None
    await cache.cache_user(user)

    assert (await cache.get_cached_user("alice")).created_at is None


async def test_redis_errors_do_not_break_the_app(broken_redis, user):
    assert await cache.get_cached_user("alice") is None
    await cache.cache_user(user)
    await cache.invalidate_user("alice")

    broken_redis.get.assert_awaited_once()
    broken_redis.set.assert_awaited_once()
    broken_redis.delete.assert_awaited_once()


async def test_get_current_user_falls_back_to_db_when_redis_is_down(
    client, user_headers, broken_redis
):
    response = await client.get("/api/users/me", headers=user_headers)

    assert response.status_code == 200
    assert response.json()["username"] == "alice"
