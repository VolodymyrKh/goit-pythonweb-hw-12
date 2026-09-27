"""Redis cache for the current user.

Only public, non-sensitive user fields are cached: the password hash and the
refresh token hash never leave the database. Entries expire after
``USER_CACHE_TTL_SECONDS`` and are removed whenever the user changes (email
confirmation, avatar, role, password, logout), so the cache never serves
stale data for long.

If Redis is unavailable the application keeps working: cache errors are
logged and requests fall back to the database.
"""

import json
import logging
from datetime import datetime

import redis.asyncio as redis
from redis.exceptions import RedisError

from src.conf.config import settings
from src.database.models import Role, User

logger = logging.getLogger(__name__)

redis_client: redis.Redis = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    password=settings.REDIS_PASSWORD,
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=2,
)


def _user_key(username: str) -> str:
    return f"user:{username}"


def _serialize_user(user: User) -> str:
    return json.dumps(
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "avatar": user.avatar,
            "confirmed": user.confirmed,
            "role": Role(user.role).value,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }
    )


def _deserialize_user(raw: str) -> User:
    data = json.loads(raw)
    data["role"] = Role(data["role"])
    if data["created_at"]:
        data["created_at"] = datetime.fromisoformat(data["created_at"])
    return User(**data)


async def get_cached_user(username: str) -> User | None:
    """Return the cached user or ``None`` on a cache miss or Redis error.

    Args:
        username: Username the user is cached under.

    Returns:
        A detached :class:`~src.database.models.User` built from the cache.
        It has no password or refresh token hash and is not bound to a
        database session.
    """
    try:
        raw = await redis_client.get(_user_key(username))
    except RedisError as err:
        logger.warning("Redis is unavailable, reading user from DB: %s", err)
        return None
    return _deserialize_user(raw) if raw else None


async def cache_user(user: User) -> None:
    """Store the user in the cache for ``USER_CACHE_TTL_SECONDS``.

    Args:
        user: User loaded from the database.
    """
    try:
        await redis_client.set(
            _user_key(user.username),
            _serialize_user(user),
            ex=settings.USER_CACHE_TTL_SECONDS,
        )
    except RedisError as err:
        logger.warning("Failed to cache user %s: %s", user.username, err)


async def invalidate_user(username: str) -> None:
    """Remove the user from the cache so the next request reads fresh data.

    Args:
        username: Username of the changed user.
    """
    try:
        await redis_client.delete(_user_key(username))
    except RedisError as err:
        logger.warning("Failed to invalidate cached user %s: %s", username, err)
