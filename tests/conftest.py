"""Shared test fixtures.

Tests never touch the real services: PostgreSQL is replaced with an in-memory
SQLite database, Redis with fakeredis, and email sending with mocks.
"""

import os

# Test settings must be set before the application modules are imported.
# Environment variables take precedence over the .env file.
os.environ.update(
    {
        "POSTGRES_USER": "test",
        "POSTGRES_PASSWORD": "test",
        "POSTGRES_DB": "test",
        "JWT_SECRET": "test-secret-key-that-is-long-enough-for-hs256",
        "MAIL_FROM": "noreply@example.com",
        "MAIL_SERVER": "localhost",
        "CLOUDINARY_NAME": "test",
        "CLOUDINARY_API_KEY": "test",
        "CLOUDINARY_API_SECRET": "test",
        "CORS_ORIGINS": "http://localhost:3000",
    }
)

from unittest.mock import AsyncMock  # noqa: E402

import fakeredis  # noqa: E402
import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from main import app  # noqa: E402
from src.database.db import get_db  # noqa: E402
from src.database.models import Base, Role, User  # noqa: E402
from src.services import cache  # noqa: E402
from src.services.auth import create_access_token, get_password_hash  # noqa: E402
from src.services.limiter import limiter  # noqa: E402

TEST_PASSWORD = "secret123"


@pytest.fixture
async def session_maker():
    """Fresh in-memory database with all tables for every test."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(autoflush=False, autocommit=False, bind=engine)
    await engine.dispose()


@pytest.fixture
async def session(session_maker):
    """Database session for preparing and checking data inside a test."""
    async with session_maker() as session:
        yield session


@pytest.fixture
async def fake_redis(monkeypatch):
    """Replace the Redis client with an in-memory fake."""
    client = fakeredis.FakeAsyncRedis(decode_responses=True)
    monkeypatch.setattr(cache, "redis_client", client)
    yield client
    await client.aclose()


@pytest.fixture
def mail_mocks(monkeypatch):
    """Replace email sending in the auth routes with mocks."""
    mocks = {
        "verification": AsyncMock(),
        "reset": AsyncMock(),
    }
    monkeypatch.setattr("src.api.auth.send_verification_email", mocks["verification"])
    monkeypatch.setattr("src.api.auth.send_password_reset_email", mocks["reset"])
    return mocks


@pytest.fixture
async def client(session_maker, fake_redis, mail_mocks):
    """HTTP client for the application with test dependencies."""

    async def override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    limiter.reset()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def create_user(session):
    """Factory that inserts a user directly into the database."""

    async def _create_user(
        username: str = "alice",
        email: str | None = None,
        password: str = TEST_PASSWORD,
        confirmed: bool = True,
        role: Role = Role.USER,
    ) -> User:
        user = User(
            username=username,
            email=email or f"{username}@example.com",
            hashed_password=get_password_hash(password),
            confirmed=confirmed,
            role=role,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

    return _create_user


def auth_headers(username: str) -> dict[str, str]:
    """Authorization header with a valid access token for the user."""
    return {"Authorization": f"Bearer {create_access_token(username)}"}


@pytest.fixture
async def user_headers(create_user):
    """Authorization headers of a confirmed regular user ``alice``."""
    await create_user("alice")
    return auth_headers("alice")


@pytest.fixture
async def admin_headers(create_user):
    """Authorization headers of a confirmed administrator ``admin``."""
    await create_user("admin", role=Role.ADMIN)
    return auth_headers("admin")
