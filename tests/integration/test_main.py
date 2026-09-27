"""Integration tests for application-level routes."""

import pytest


@pytest.mark.parametrize("method", ["GET", "HEAD"])
async def test_root_redirects_to_docs(client, method):
    response = await client.request(method, "/")

    assert response.status_code == 307
    assert response.headers["location"] == "/docs"


async def test_root_is_hidden_from_openapi(client):
    schema = (await client.get("/openapi.json")).json()

    assert "/" not in schema["paths"]
