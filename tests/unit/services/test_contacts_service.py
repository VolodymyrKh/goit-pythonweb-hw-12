"""Unit tests for ContactService error handling."""

from datetime import date
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from src.database.models import User
from src.schemas import ContactCreate, ContactUpdate
from src.services.contacts import ContactService


@pytest.fixture
def service():
    service = ContactService(AsyncMock())
    service.repository = AsyncMock()
    service.repository.get_contact_by_email.return_value = None
    return service


@pytest.fixture
def user():
    return User(id=1, username="alice")


def integrity_error():
    return IntegrityError("INSERT", {}, Exception("unique violation"))


async def test_create_contact_race_condition_returns_409(service, user):
    """Two parallel requests can pass the pre-check; the DB constraint still catches it."""
    service.repository.create_contact.side_effect = integrity_error()
    body = ContactCreate(
        first_name="Ivan",
        last_name="Petrenko",
        email="ivan@example.com",
        phone="+380501234567",
        birthday=date(1990, 5, 20),
    )

    with pytest.raises(HTTPException) as exc:
        await service.create_contact(body, user)

    assert exc.value.status_code == 409
    service.repository.db.rollback.assert_awaited_once()


async def test_update_contact_race_condition_returns_409(service, user):
    service.repository.update_contact.side_effect = integrity_error()

    with pytest.raises(HTTPException) as exc:
        await service.update_contact(1, ContactUpdate(email="ivan@example.com"), user)

    assert exc.value.status_code == 409
    service.repository.db.rollback.assert_awaited_once()
