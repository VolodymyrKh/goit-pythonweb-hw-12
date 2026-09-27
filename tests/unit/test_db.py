"""Unit tests for database session management and the health check."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.exc import OperationalError

from src.database import db
from src.database.db import DatabaseSessionManager


async def test_session_rolls_back_on_database_error():
    manager = DatabaseSessionManager("sqlite+aiosqlite:///:memory:")
    session = AsyncMock()
    manager._session_maker = lambda: session

    with pytest.raises(OperationalError):
        async with manager.session():
            raise OperationalError("SELECT 1", {}, Exception("connection lost"))

    session.rollback.assert_awaited_once()
    session.close.assert_awaited_once()


async def test_session_without_session_maker_raises():
    manager = DatabaseSessionManager("sqlite+aiosqlite:///:memory:")
    manager._session_maker = None

    with pytest.raises(Exception, match="not initialized"):
        async with manager.session():
            pass


async def test_get_db_yields_session():
    manager = DatabaseSessionManager("sqlite+aiosqlite:///:memory:")
    with patch.object(db, "sessionmanager", manager):
        generator = db.get_db()
        session = await anext(generator)
        assert session is not None
        await generator.aclose()


async def test_healthchecker_reports_db_errors(client):
    from main import app
    from src.database.db import get_db

    async def broken_db():
        session = AsyncMock()
        session.execute.side_effect = OperationalError("SELECT 1", {}, Exception("down"))
        yield session

    app.dependency_overrides[get_db] = broken_db

    response = await client.get("/api/healthchecker")

    assert response.status_code == 500
    assert response.json() == {"detail": "Error connecting to the database"}
