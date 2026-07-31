from __future__ import annotations

from uuid import UUID

import httpx

from gilbic_backend.auth_client import SupabaseAuthClient, SupabaseAuthError
from gilbic_backend.config import Settings


AUTH_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def settings() -> Settings:
    return Settings(
        database_url="postgresql://127.0.0.1:5432/test",
        supabase_url="https://project.supabase.co",
        supabase_publishable_key="sb_publishable_test",
    )


def test_sign_in_uses_password_grant_and_publishable_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/auth/v1/token"
        assert request.url.params["grant_type"] == "password"
        assert request.headers["apikey"] == "sb_publishable_test"
        return httpx.Response(
            200,
            json={
                "access_token": "access",
                "refresh_token": "refresh",
                "expires_in": 3600,
                "user": {
                    "id": AUTH_ID,
                    "email": "user@example.com",
                    "email_confirmed_at": "2026-07-31T00:00:00Z",
                },
            },
        )

    http = httpx.Client(
        base_url="https://project.supabase.co",
        transport=httpx.MockTransport(handler),
    )
    client = SupabaseAuthClient(settings(), client=http)

    session = client.sign_in(email="user@example.com", password="secret-pass")

    assert session.auth_user_id == UUID(AUTH_ID)
    assert session.access_token == "access"
    assert session.refresh_token == "refresh"
    assert session.email_confirmed is True


def test_get_user_sends_bearer_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/auth/v1/user"
        assert request.headers["Authorization"] == "Bearer access"
        assert request.headers["apikey"] == "sb_publishable_test"
        return httpx.Response(
            200,
            json={
                "id": AUTH_ID,
                "email": "user@example.com",
                "email_confirmed_at": "2026-07-31T00:00:00Z",
            },
        )

    http = httpx.Client(
        base_url="https://project.supabase.co",
        transport=httpx.MockTransport(handler),
    )
    client = SupabaseAuthClient(settings(), client=http)

    identity = client.get_user(access_token="access")

    assert identity.auth_user_id == UUID(AUTH_ID)
    assert identity.email == "user@example.com"


def test_auth_error_does_not_require_secret_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["apikey"] == "sb_publishable_test"
        return httpx.Response(
            400,
            json={"code": "invalid_credentials", "message": "Invalid login credentials"},
        )

    http = httpx.Client(
        base_url="https://project.supabase.co",
        transport=httpx.MockTransport(handler),
    )
    client = SupabaseAuthClient(settings(), client=http)

    try:
        client.sign_in(email="user@example.com", password="wrong")
    except SupabaseAuthError as exc:
        assert exc.status_code == 400
        assert exc.code == "invalid_credentials"
    else:
        raise AssertionError("Expected SupabaseAuthError")
