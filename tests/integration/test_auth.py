"""Integration tests for /api/auth routes."""

from sqlalchemy import select

from src.database.models import User
from src.services.auth import (
    create_email_token,
    create_refresh_token,
    create_reset_password_token,
    verify_password,
)
from tests.conftest import TEST_PASSWORD, auth_headers

REGISTER_BODY = {"username": "alice", "email": "alice@example.com", "password": TEST_PASSWORD}


async def login(client, username="alice", password=TEST_PASSWORD):
    return await client.post(
        "/api/auth/login", data={"username": username, "password": password}
    )


async def get_user(session, username="alice") -> User:
    session.expire_all()
    result = await session.execute(select(User).where(User.username == username))
    return result.scalar_one()


# --- registration ---------------------------------------------------------


async def test_register_returns_201_and_user(client, session, mail_mocks):
    response = await client.post("/api/auth/register", json=REGISTER_BODY)

    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "alice"
    assert data["email"] == "alice@example.com"
    assert data["confirmed"] is False
    assert data["role"] == "user"
    assert "gravatar.com" in data["avatar"]
    assert "password" not in data and "hashed_password" not in data

    user = await get_user(session)
    assert user.hashed_password != TEST_PASSWORD
    assert verify_password(TEST_PASSWORD, user.hashed_password)
    mail_mocks["verification"].assert_awaited_once_with(
        "alice@example.com", "alice", "http://test/"
    )


async def test_register_duplicate_email_returns_409(client, create_user):
    await create_user("someone", email="alice@example.com")

    response = await client.post("/api/auth/register", json=REGISTER_BODY)

    assert response.status_code == 409


async def test_register_duplicate_username_returns_409(client, create_user):
    await create_user("alice", email="other@example.com")

    response = await client.post("/api/auth/register", json=REGISTER_BODY)

    assert response.status_code == 409


async def test_register_invalid_body_returns_422(client):
    response = await client.post(
        "/api/auth/register",
        json={"username": "a", "email": "not-an-email", "password": "1"},
    )

    assert response.status_code == 422


# --- login ----------------------------------------------------------------


async def test_login_returns_token_pair(client, session, create_user):
    await create_user("alice")

    response = await login(client)

    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"] and data["refresh_token"]
    user = await get_user(session)
    assert user.refresh_token_hash is not None
    assert user.refresh_token_hash != data["refresh_token"]


async def test_login_wrong_password_returns_401(client, create_user):
    await create_user("alice")

    response = await login(client, password="wrong-password")

    assert response.status_code == 401


async def test_login_unknown_user_returns_401(client):
    response = await login(client, username="ghost")

    assert response.status_code == 401


async def test_login_unconfirmed_email_returns_401(client, create_user):
    await create_user("alice", confirmed=False)

    response = await login(client)

    assert response.status_code == 401
    assert response.json()["detail"] == "Email is not confirmed"


# --- refresh tokens and logout -------------------------------------------


async def test_refresh_rotates_tokens(client, create_user):
    await create_user("alice")
    tokens = (await login(client)).json()

    response = await client.post(
        "/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )

    assert response.status_code == 200
    new_tokens = response.json()
    assert new_tokens["refresh_token"] != tokens["refresh_token"]
    me = await client.get(
        "/api/users/me", headers={"Authorization": f"Bearer {new_tokens['access_token']}"}
    )
    assert me.status_code == 200

    # The old refresh token was rotated out and cannot be reused
    reuse = await client.post(
        "/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert reuse.status_code == 401


async def test_refresh_with_access_token_returns_401(client, create_user):
    await create_user("alice")
    tokens = (await login(client)).json()

    response = await client.post(
        "/api/auth/refresh", json={"refresh_token": tokens["access_token"]}
    )

    assert response.status_code == 401


async def test_refresh_with_invalid_token_returns_401(client):
    response = await client.post("/api/auth/refresh", json={"refresh_token": "garbage"})

    assert response.status_code == 401


async def test_refresh_for_unknown_user_returns_401(client):
    response = await client.post(
        "/api/auth/refresh", json={"refresh_token": create_refresh_token("ghost")}
    )

    assert response.status_code == 401


async def test_logout_revokes_refresh_token(client, session, create_user):
    await create_user("alice")
    tokens = (await login(client)).json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    response = await client.post("/api/auth/logout", headers=headers)

    assert response.status_code == 200
    assert (await get_user(session)).refresh_token_hash is None
    refresh = await client.post(
        "/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refresh.status_code == 401


# --- email confirmation ---------------------------------------------------


async def test_confirm_email(client, session, create_user):
    await create_user("alice", confirmed=False)

    response = await client.get(
        f"/api/auth/confirmed_email/{create_email_token('alice@example.com')}"
    )

    assert response.status_code == 200
    assert response.json() == {"message": "Email confirmed"}
    assert (await get_user(session)).confirmed is True


async def test_confirm_email_already_confirmed(client, create_user):
    await create_user("alice")

    response = await client.get(
        f"/api/auth/confirmed_email/{create_email_token('alice@example.com')}"
    )

    assert response.json() == {"message": "Your email is already confirmed"}


async def test_confirm_email_invalid_token_returns_400(client):
    response = await client.get("/api/auth/confirmed_email/garbage")

    assert response.status_code == 400


async def test_confirm_email_unknown_user_returns_400(client):
    response = await client.get(
        f"/api/auth/confirmed_email/{create_email_token('ghost@example.com')}"
    )

    assert response.status_code == 400


async def test_email_token_cannot_be_used_as_access_token(client, create_user):
    await create_user("alice")
    headers = {"Authorization": f"Bearer {create_email_token('alice@example.com')}"}

    response = await client.get("/api/users/me", headers=headers)

    assert response.status_code == 401


async def test_request_email_sends_new_link(client, create_user, mail_mocks):
    await create_user("alice", confirmed=False)

    response = await client.post(
        "/api/auth/request_email", json={"email": "alice@example.com"}
    )

    assert response.status_code == 200
    mail_mocks["verification"].assert_awaited_once()


async def test_request_email_already_confirmed(client, create_user, mail_mocks):
    await create_user("alice")

    response = await client.post(
        "/api/auth/request_email", json={"email": "alice@example.com"}
    )

    assert response.json() == {"message": "Your email is already confirmed"}
    mail_mocks["verification"].assert_not_awaited()


async def test_request_email_unknown_user_gives_same_answer(client, mail_mocks):
    response = await client.post(
        "/api/auth/request_email", json={"email": "ghost@example.com"}
    )

    assert response.status_code == 200
    assert response.json() == {"message": "Check your email for confirmation"}
    mail_mocks["verification"].assert_not_awaited()


# --- password reset -------------------------------------------------------


async def test_request_password_reset_sends_email(client, create_user, mail_mocks):
    await create_user("alice")

    response = await client.post(
        "/api/auth/request_password_reset", json={"email": "alice@example.com"}
    )

    assert response.status_code == 200
    mail_mocks["reset"].assert_awaited_once()
    email, username, host, token = mail_mocks["reset"].call_args.args
    assert (email, username, host) == ("alice@example.com", "alice", "http://test/")
    assert token


async def test_request_password_reset_unknown_email_gives_same_answer(client, mail_mocks):
    response = await client.post(
        "/api/auth/request_password_reset", json={"email": "ghost@example.com"}
    )

    assert response.status_code == 200
    assert "If this email is registered" in response.json()["message"]
    mail_mocks["reset"].assert_not_awaited()


async def test_reset_password_form_page(client, create_user):
    user = await create_user("alice")
    token = create_reset_password_token(user)

    response = await client.get(f"/api/auth/reset_password/{token}")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "new password" in response.text.lower()
    assert f'data-token="{token}"' in response.text
    assert 'data-action="http://test/api/auth/reset_password"' in response.text


async def test_reset_password_form_invalid_token_returns_400(client):
    response = await client.get("/api/auth/reset_password/garbage")

    assert response.status_code == 400


async def test_reset_password_full_flow(client, session, create_user):
    user = await create_user("alice")
    tokens = (await login(client)).json()
    reset_token = create_reset_password_token(user)

    response = await client.post(
        "/api/auth/reset_password",
        json={"token": reset_token, "new_password": "brand-new-password"},
    )

    assert response.status_code == 200
    assert (await login(client, password=TEST_PASSWORD)).status_code == 401
    assert (await login(client, password="brand-new-password")).status_code == 200

    # The reset link is single-use
    reuse = await client.post(
        "/api/auth/reset_password",
        json={"token": reset_token, "new_password": "another-password"},
    )
    assert reuse.status_code == 400

    # The refresh token issued before the reset was revoked
    refresh = await client.post(
        "/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refresh.status_code == 401


async def test_reset_password_invalid_token_returns_400(client):
    response = await client.post(
        "/api/auth/reset_password",
        json={"token": "garbage", "new_password": "brand-new-password"},
    )

    assert response.status_code == 400


async def test_reset_password_unknown_user_returns_400(client):
    ghost = User(email="ghost@example.com", hashed_password="x")

    response = await client.post(
        "/api/auth/reset_password",
        json={"token": create_reset_password_token(ghost), "new_password": "brand-new-password"},
    )

    assert response.status_code == 400


async def test_reset_password_too_short_returns_422(client, create_user):
    user = await create_user("alice")

    response = await client.post(
        "/api/auth/reset_password",
        json={"token": create_reset_password_token(user), "new_password": "123"},
    )

    assert response.status_code == 422


async def test_reset_token_cannot_be_used_as_access_token(client, create_user):
    user = await create_user("alice")
    headers = {"Authorization": f"Bearer {create_reset_password_token(user)}"}

    response = await client.get("/api/users/me", headers=headers)

    assert response.status_code == 401


async def test_access_token_for_deleted_user_returns_401(client):
    response = await client.get("/api/users/me", headers=auth_headers("ghost"))

    assert response.status_code == 401
