"""Integration tests for /api/users routes, roles and the user cache."""

import json
from unittest.mock import patch

from src.database.models import Role
from tests.conftest import auth_headers

PNG = ("avatar.png", b"\x89PNG\r\n\x1a\nfake", "image/png")


async def test_me_returns_current_user(client, user_headers):
    response = await client.get("/api/users/me", headers=user_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "alice"
    assert data["role"] == "user"


async def test_me_without_token_returns_401(client):
    response = await client.get("/api/users/me")

    assert response.status_code == 401


async def test_me_is_rate_limited(client, user_headers):
    codes = [
        (await client.get("/api/users/me", headers=user_headers)).status_code
        for _ in range(11)
    ]

    assert codes[:10] == [200] * 10
    assert codes[10] == 429
    assert (await client.get("/api/users/me", headers=user_headers)).json() == {
        "detail": "Too many requests. Try again later."
    }


# --- cache ----------------------------------------------------------------


async def test_current_user_is_cached_without_secrets(client, user_headers, fake_redis):
    await client.get("/api/users/me", headers=user_headers)

    cached = json.loads(await fake_redis.get("user:alice"))
    assert cached["username"] == "alice"
    assert "hashed_password" not in cached
    assert "refresh_token_hash" not in cached
    assert 0 < await fake_redis.ttl("user:alice") <= 900


async def test_current_user_is_read_from_cache(client, user_headers):
    await client.get("/api/users/me", headers=user_headers)

    with patch("src.services.auth.UserRepository.get_user_by_username") as db_lookup:
        response = await client.get("/api/users/me", headers=user_headers)

    assert response.status_code == 200
    assert response.json()["username"] == "alice"
    db_lookup.assert_not_called()


# --- avatar ---------------------------------------------------------------


async def test_regular_user_cannot_change_avatar(client, user_headers):
    response = await client.patch(
        "/api/users/avatar", headers=user_headers, files={"file": PNG}
    )

    assert response.status_code == 403


async def test_admin_can_change_avatar(client, admin_headers, fake_redis):
    await client.get("/api/users/me", headers=admin_headers)  # warm up the cache
    url = "https://res.cloudinary.com/test/image/upload/v1/ContactsApp/admin"

    with patch(
        "src.api.users.UploadFileService.upload_file", return_value=url
    ) as upload:
        response = await client.patch(
            "/api/users/avatar", headers=admin_headers, files={"file": PNG}
        )

    assert response.status_code == 200
    assert response.json()["avatar"] == url
    assert upload.call_args.args[1] == "admin"
    # The cached user was dropped, so /me returns the new avatar
    assert await fake_redis.get("user:admin") is None
    me = await client.get("/api/users/me", headers=admin_headers)
    assert me.json()["avatar"] == url


async def test_avatar_must_be_an_image(client, admin_headers):
    response = await client.patch(
        "/api/users/avatar",
        headers=admin_headers,
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 415


async def test_avatar_too_large(client, admin_headers):
    big = ("big.png", b"0" * (5 * 1024 * 1024 + 1), "image/png")

    response = await client.patch("/api/users/avatar", headers=admin_headers, files={"file": big})

    assert response.status_code == 413


async def test_avatar_without_token_returns_401(client):
    response = await client.patch("/api/users/avatar", files={"file": PNG})

    assert response.status_code == 401


# --- roles ----------------------------------------------------------------


async def test_admin_can_change_role(client, admin_headers, create_user, fake_redis):
    user = await create_user("bob")
    bob_headers = auth_headers("bob")
    await client.get("/api/users/me", headers=bob_headers)  # cache bob as a regular user

    response = await client.patch(
        f"/api/users/{user.id}/role", headers=admin_headers, json={"role": "admin"}
    )

    assert response.status_code == 200
    assert response.json()["role"] == "admin"
    # The cache was invalidated, so the new role takes effect immediately
    me = await client.get("/api/users/me", headers=bob_headers)
    assert me.json()["role"] == "admin"


async def test_regular_user_cannot_change_role(client, user_headers, create_user):
    bob = await create_user("bob")

    response = await client.patch(
        f"/api/users/{bob.id}/role", headers=user_headers, json={"role": "admin"}
    )

    assert response.status_code == 403


async def test_admin_cannot_demote_themselves(client, admin_headers):
    me = (await client.get("/api/users/me", headers=admin_headers)).json()

    response = await client.patch(
        f"/api/users/{me['id']}/role", headers=admin_headers, json={"role": "user"}
    )

    assert response.status_code == 400


async def test_change_role_unknown_user_returns_404(client, admin_headers):
    response = await client.patch(
        "/api/users/999/role", headers=admin_headers, json={"role": "admin"}
    )

    assert response.status_code == 404


async def test_change_role_invalid_value_returns_422(client, admin_headers, create_user):
    bob = await create_user("bob")

    response = await client.patch(
        f"/api/users/{bob.id}/role", headers=admin_headers, json={"role": "superuser"}
    )

    assert response.status_code == 422


async def test_new_users_have_user_role(client, create_user):
    user = await create_user("carol")

    assert user.role == Role.USER
