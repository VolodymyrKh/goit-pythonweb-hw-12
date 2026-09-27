"""Integration tests for /api/contacts routes."""

from datetime import date, timedelta

import pytest

from tests.conftest import auth_headers


def contact_body(**overrides) -> dict:
    body = {
        "first_name": "Volodymyr",
        "last_name": "Kheroim",
        "email": "volodymyr@example.com",
        "phone": "+380501234567",
        "birthday": "1990-05-20",
        "additional_data": "Developer",
    }
    body.update(overrides)
    return body


def birthday_in(days: int) -> str:
    """Birthday (born in 1990) that comes ``days`` days from today."""
    return (date.today() + timedelta(days=days)).replace(year=1990).isoformat()


@pytest.fixture
async def create_contact(client, user_headers):
    async def _create(**overrides) -> dict:
        response = await client.post(
            "/api/contacts/", json=contact_body(**overrides), headers=user_headers
        )
        assert response.status_code == 201, response.text
        return response.json()

    return _create


async def test_contacts_require_token(client):
    assert (await client.get("/api/contacts/")).status_code == 401
    assert (await client.post("/api/contacts/", json=contact_body())).status_code == 401


async def test_create_contact_returns_201(client, user_headers):
    response = await client.post("/api/contacts/", json=contact_body(), headers=user_headers)

    assert response.status_code == 201
    data = response.json()
    assert data["id"] > 0
    assert data["email"] == "volodymyr@example.com"
    assert data["additional_data"] == "Developer"


async def test_create_contact_duplicate_email_returns_409(client, user_headers, create_contact):
    await create_contact()

    response = await client.post("/api/contacts/", json=contact_body(), headers=user_headers)

    assert response.status_code == 409


async def test_create_contact_invalid_body_returns_422(client, user_headers):
    response = await client.post(
        "/api/contacts/", json=contact_body(email="bad", phone="abc"), headers=user_headers
    )

    assert response.status_code == 422


async def test_list_contacts(client, user_headers, create_contact):
    await create_contact()
    await create_contact(first_name="Olena", email="olena@example.com")

    response = await client.get("/api/contacts/", headers=user_headers)

    assert response.status_code == 200
    assert [c["first_name"] for c in response.json()] == ["Volodymyr", "Olena"]


async def test_list_contacts_pagination(client, user_headers, create_contact):
    for i in range(3):
        await create_contact(first_name=f"Name{i}", email=f"c{i}@example.com")

    response = await client.get("/api/contacts/?skip=1&limit=1", headers=user_headers)

    assert [c["first_name"] for c in response.json()] == ["Name1"]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("first_name=volod", ["Volodymyr"]),
        ("last_name=SHEV", ["Olena"]),
        ("email=example.com", ["Volodymyr", "Olena"]),
        ("first_name=nobody", []),
    ],
)
async def test_search_contacts(client, user_headers, create_contact, query, expected):
    await create_contact()
    await create_contact(first_name="Olena", last_name="Shevchenko", email="olena@example.com")

    response = await client.get(f"/api/contacts/?{query}", headers=user_headers)

    assert [c["first_name"] for c in response.json()] == expected


async def test_get_contact(client, user_headers, create_contact):
    contact = await create_contact()

    response = await client.get(f"/api/contacts/{contact['id']}", headers=user_headers)

    assert response.status_code == 200
    assert response.json()["email"] == "volodymyr@example.com"


async def test_get_contact_not_found(client, user_headers):
    response = await client.get("/api/contacts/999", headers=user_headers)

    assert response.status_code == 404


async def test_update_contact(client, user_headers, create_contact):
    contact = await create_contact()

    response = await client.put(
        f"/api/contacts/{contact['id']}",
        json={"phone": "+380991112233"},
        headers=user_headers,
    )

    assert response.status_code == 200
    assert response.json()["phone"] == "+380991112233"
    assert response.json()["first_name"] == "Volodymyr"


async def test_update_contact_email_conflict_returns_409(client, user_headers, create_contact):
    await create_contact()
    other = await create_contact(email="other@example.com")

    response = await client.put(
        f"/api/contacts/{other['id']}", json={"email": "volodymyr@example.com"}, headers=user_headers
    )

    assert response.status_code == 409


async def test_update_contact_not_found(client, user_headers):
    response = await client.put(
        "/api/contacts/999", json={"phone": "+380991112233"}, headers=user_headers
    )

    assert response.status_code == 404


async def test_delete_contact(client, user_headers, create_contact):
    contact = await create_contact()

    response = await client.delete(f"/api/contacts/{contact['id']}", headers=user_headers)

    assert response.status_code == 200
    assert (await client.get(f"/api/contacts/{contact['id']}", headers=user_headers)).status_code == 404


async def test_delete_contact_not_found(client, user_headers):
    response = await client.delete("/api/contacts/999", headers=user_headers)

    assert response.status_code == 404


async def test_upcoming_birthdays(client, user_headers, create_contact):
    await create_contact(first_name="InThreeDays", email="a@example.com", birthday=birthday_in(3))
    await create_contact(first_name="Today", email="b@example.com", birthday=birthday_in(0))
    await create_contact(first_name="LastDay", email="c@example.com", birthday=birthday_in(6))
    await create_contact(first_name="TooLate", email="d@example.com", birthday=birthday_in(7))

    response = await client.get("/api/contacts/birthdays", headers=user_headers)

    assert response.status_code == 200
    assert [c["first_name"] for c in response.json()] == ["Today", "InThreeDays", "LastDay"]


async def test_upcoming_birthdays_custom_days(client, user_headers, create_contact):
    await create_contact(first_name="InTenDays", birthday=birthday_in(10))

    short = await client.get("/api/contacts/birthdays", headers=user_headers)
    long = await client.get("/api/contacts/birthdays?days=11", headers=user_headers)

    assert short.json() == []
    assert [c["first_name"] for c in long.json()] == ["InTenDays"]


async def test_users_see_only_their_own_contacts(client, create_user, create_contact):
    contact = await create_contact(birthday=birthday_in(1))
    await create_user("bob")
    bob = auth_headers("bob")

    assert (await client.get("/api/contacts/", headers=bob)).json() == []
    assert (await client.get("/api/contacts/birthdays", headers=bob)).json() == []
    assert (await client.get(f"/api/contacts/{contact['id']}", headers=bob)).status_code == 404
    assert (
        await client.put(f"/api/contacts/{contact['id']}", json={"phone": "+380000000000"}, headers=bob)
    ).status_code == 404
    assert (await client.delete(f"/api/contacts/{contact['id']}", headers=bob)).status_code == 404

    # Another user may store a contact with the same email
    response = await client.post("/api/contacts/", json=contact_body(), headers=bob)
    assert response.status_code == 201


async def test_healthchecker(client):
    response = await client.get("/api/healthchecker")

    assert response.status_code == 200


async def test_cors_headers(client):
    allowed = await client.options(
        "/api/contacts/",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )
    foreign = await client.options(
        "/api/contacts/",
        headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "GET"},
    )

    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-origin" not in foreign.headers
