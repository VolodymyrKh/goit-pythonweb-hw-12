"""Unit tests for the set_role command-line tool."""

import contextlib

import pytest
from sqlalchemy import select

from src.database.models import Role, User
from src.scripts import set_role as set_role_module


@pytest.fixture
def use_test_db(monkeypatch, session_maker, fake_redis):
    class TestSessionManager:
        @contextlib.asynccontextmanager
        async def session(self):
            async with session_maker() as session:
                yield session

    monkeypatch.setattr(set_role_module, "sessionmanager", TestSessionManager())


async def test_set_role(use_test_db, create_user, session):
    await create_user("alice")

    assert await set_role_module.set_role("alice", Role.ADMIN) is True

    session.expire_all()
    user = (await session.execute(select(User).where(User.username == "alice"))).scalar_one()
    assert user.role == Role.ADMIN


async def test_set_role_unknown_user(use_test_db):
    assert await set_role_module.set_role("ghost", Role.ADMIN) is False


@pytest.mark.parametrize(("found", "exit_code"), [(True, 0), (False, 1)])
def test_main(monkeypatch, capsys, found, exit_code):
    calls = []

    async def fake_set_role(username, role):
        calls.append((username, role))
        return found

    monkeypatch.setattr(set_role_module, "set_role", fake_set_role)

    assert set_role_module.main(["alice", "admin"]) == exit_code
    assert calls == [("alice", Role.ADMIN)]
    assert "alice" in capsys.readouterr().out
