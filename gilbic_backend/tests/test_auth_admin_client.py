from __future__ import annotations

import json
from uuid import UUID

import httpx
import pytest

from gilbic_backend.auth_admin_client import SupabaseAuthAdminClient
from gilbic_backend.auth_client import SupabaseAuthError
from gilbic_backend.config import Settings


INVITED_ID = UUID("44444444-4444-4444-8444-444444444444")
CREATED_ID = UUID("55555555-5555-4555-8555-555555555555")


def _settings() -> Settings:
    return Settings(
        supabase_url="https://project.supabase.co",
        supabase_publishable_key="sb_publishable_test",
        supabase_secret_key="sb_secret_test",
        staff_invite_redirect_url="https://gilbic.example.com/set-password",
    )


def test_invite_uses_server_secret_and_redirect() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/auth/v1/invite"
        assert request.url.params["redirect_to"] == "https://gilbic.example.com/set-password"
        assert request.headers["apikey"] == "sb_secret_test"
        assert request.headers["authorization"] == "Bearer sb_secret_test"
        assert json.loads(request.content) == {"email": "collector@example.com"}
        return httpx.Response(
            200,
            json={"id": str(INVITED_ID), "email": "collector@example.com"},
        )

    settings = _settings()
    client = httpx.Client(
        base_url=settings.supabase_url,
        transport=httpx.MockTransport(handler),
    )
    admin = SupabaseAuthAdminClient(settings, client=client)

    assert admin.invite_user(email="Collector@Example.com") == INVITED_ID


def test_create_confirmed_user_uses_admin_endpoint_and_password() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/auth/v1/admin/users"
        assert request.headers["apikey"] == "sb_secret_test"
        assert json.loads(request.content) == {
            "email": "employee@example.com",
            "password": "Temporary-Password-123!",
            "email_confirm": True,
        }
        return httpx.Response(201, json={"id": str(CREATED_ID)})

    settings = _settings()
    admin = SupabaseAuthAdminClient(
        settings,
        client=httpx.Client(base_url=settings.supabase_url, transport=httpx.MockTransport(handler)),
    )

    assert admin.create_confirmed_user(
        email="Employee@Example.com",
        password="Temporary-Password-123!",
    ) == CREATED_ID


def test_update_password_uses_admin_user_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PUT"
        assert request.url.path == f"/auth/v1/admin/users/{CREATED_ID}"
        assert json.loads(request.content) == {"password": "Rotated-Password-456!"}
        return httpx.Response(200, json={"id": str(CREATED_ID)})

    settings = _settings()
    admin = SupabaseAuthAdminClient(
        settings,
        client=httpx.Client(base_url=settings.supabase_url, transport=httpx.MockTransport(handler)),
    )

    admin.update_password(
        auth_user_id=CREATED_ID,
        password="Rotated-Password-456!",
    )


def test_admin_client_requires_server_secret() -> None:
    settings = Settings(
        supabase_url="https://project.supabase.co",
        supabase_publishable_key="sb_publishable_test",
        supabase_secret_key="",
    )

    with pytest.raises(SupabaseAuthError) as exc_info:
        SupabaseAuthAdminClient(settings)

    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "auth_admin_not_configured"
