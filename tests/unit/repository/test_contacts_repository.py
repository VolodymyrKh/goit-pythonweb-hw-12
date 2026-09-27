"""Unit tests for ContactRepository with a mocked database session."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Contact, User
from src.repository.contacts import ContactRepository, _is_leap
from src.schemas import ContactCreate, ContactUpdate


@pytest.fixture
def mock_session():
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def repository(mock_session):
    return ContactRepository(mock_session)


@pytest.fixture
def user():
    return User(id=1, username="alice", email="alice@example.com")


def make_contact(**overrides) -> Contact:
    data = {
        "id": 1,
        "first_name": "Ivan",
        "last_name": "Petrenko",
        "email": "ivan@example.com",
        "phone": "+380501234567",
        "birthday": date(1990, 5, 20),
        "user_id": 1,
    }
    data.update(overrides)
    return Contact(**data)


def mock_result(mock_session, *, all_=None, one=None):
    """Make ``session.execute`` return a result with the given rows."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = all_ or []
    result.scalar_one_or_none.return_value = one
    mock_session.execute = AsyncMock(return_value=result)


def compiled_sql(mock_session) -> str:
    stmt = mock_session.execute.call_args.args[0]
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))


async def test_get_contacts_filters_by_owner(repository, mock_session, user):
    contacts = [make_contact()]
    mock_result(mock_session, all_=contacts)

    result = await repository.get_contacts(user, skip=0, limit=10)

    assert result == contacts
    sql = compiled_sql(mock_session)
    assert "contacts.user_id = 1" in sql
    assert "LIMIT 10" in sql


async def test_get_contacts_applies_search_filters(repository, mock_session, user):
    mock_result(mock_session)

    await repository.get_contacts(
        user, skip=5, limit=10, first_name="iv", last_name="pet", email="example"
    )

    sql = compiled_sql(mock_session).lower()
    assert "contacts.first_name) like lower('%iv%')" in sql
    assert "contacts.last_name) like lower('%pet%')" in sql
    assert "contacts.email) like lower('%example%')" in sql
    assert "offset 5" in sql


async def test_get_contact_by_id(repository, mock_session, user):
    contact = make_contact()
    mock_result(mock_session, one=contact)

    result = await repository.get_contact_by_id(1, user)

    assert result is contact
    sql = compiled_sql(mock_session)
    assert "contacts.id = 1" in sql and "contacts.user_id = 1" in sql


async def test_get_contact_by_id_not_found(repository, mock_session, user):
    mock_result(mock_session, one=None)

    assert await repository.get_contact_by_id(99, user) is None


async def test_get_contact_by_email(repository, mock_session, user):
    contact = make_contact()
    mock_result(mock_session, one=contact)

    result = await repository.get_contact_by_email("ivan@example.com", user)

    assert result is contact
    assert "contacts.user_id = 1" in compiled_sql(mock_session)


async def test_create_contact(repository, mock_session, user):
    body = ContactCreate(
        first_name="Ivan",
        last_name="Petrenko",
        email="ivan@example.com",
        phone="+380501234567",
        birthday=date(1990, 5, 20),
    )

    result = await repository.create_contact(body, user)

    assert isinstance(result, Contact)
    assert result.first_name == "Ivan"
    assert result.user_id == user.id
    mock_session.add.assert_called_once_with(result)
    mock_session.commit.assert_awaited_once()
    mock_session.refresh.assert_awaited_once_with(result)


async def test_update_contact_changes_only_provided_fields(repository, mock_session, user):
    contact = make_contact()
    mock_result(mock_session, one=contact)

    result = await repository.update_contact(
        1, ContactUpdate(phone="+380991112233"), user
    )

    assert result is contact
    assert contact.phone == "+380991112233"
    assert contact.first_name == "Ivan"
    mock_session.commit.assert_awaited_once()
    mock_session.refresh.assert_awaited_once_with(contact)


async def test_update_contact_not_found(repository, mock_session, user):
    mock_result(mock_session, one=None)

    result = await repository.update_contact(1, ContactUpdate(phone="+380991112233"), user)

    assert result is None
    mock_session.commit.assert_not_awaited()


async def test_remove_contact(repository, mock_session, user):
    contact = make_contact()
    mock_result(mock_session, one=contact)

    result = await repository.remove_contact(1, user)

    assert result is contact
    mock_session.delete.assert_awaited_once_with(contact)
    mock_session.commit.assert_awaited_once()


async def test_remove_contact_not_found(repository, mock_session, user):
    mock_result(mock_session, one=None)

    assert await repository.remove_contact(1, user) is None
    mock_session.delete.assert_not_awaited()


async def test_upcoming_birthdays_sorted_by_next_birthday(repository, mock_session, user):
    later = make_contact(id=1, birthday=date(1985, 1, 2))
    sooner = make_contact(id=2, birthday=date(2000, 12, 30))
    mock_result(mock_session, all_=[later, sooner])

    result = await repository.get_upcoming_birthdays(7, user, today=date(2026, 12, 29))

    assert result == [sooner, later]
    assert "contacts.user_id = 1" in compiled_sql(mock_session)


async def test_upcoming_birthdays_covers_exactly_n_days(repository, mock_session, user):
    mock_result(mock_session)

    await repository.get_upcoming_birthdays(7, user, today=date(2026, 12, 29))

    sql = compiled_sql(mock_session).lower()
    # One (month, day) condition per day: 29.12 .. 04.01, the 8th day (05.01) is excluded
    assert sql.count("extract(month from contacts.birthday)") == 7
    assert "extract(day from contacts.birthday) = 4" in sql
    assert "extract(day from contacts.birthday) = 5" not in sql


async def test_upcoming_birthdays_feb_29_in_non_leap_year(repository, mock_session, user):
    leapling = make_contact(birthday=date(2000, 2, 29))
    mock_result(mock_session, all_=[leapling])

    result = await repository.get_upcoming_birthdays(3, user, today=date(2027, 2, 27))

    assert result == [leapling]
    assert "= 29" in compiled_sql(mock_session)


@pytest.mark.parametrize(
    ("year", "expected"), [(2024, True), (2027, False), (1900, False), (2000, True)]
)
def test_is_leap(year, expected):
    assert _is_leap(year) is expected
