from __future__ import annotations

import json
from uuid import UUID

import httpx

from gilbic_backend.auth_admin_client import SupabaseAuthAdminClient
from gilbic_backend.config import Settings


AUTH_USER_ID = UUID("44444444-4444-4444-8444-444444444444")


def _settings() -> Settings:
    return Settings(
        supabase_url="https://project.supabase.co",
        supabase_publishable_key="sb_publishable_test",
        supabase_secret_key="sb_secret_test",
    )


def test_create_user_posts_generated_password_to_server_only_admin_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/auth/v1/admin/users"
        assert request.headers["apikey"] == "sb_secret_test"
        assert request.headers["authorization"] == "Bearer sb_secret_test"
        assert json.loads(request.content) == {
            "email": "client@example.com",
            "password": "Generated@Pass9",
            "email_confirm": True,
        }
        return httpx.Response(
            200,
            json={"id": str(AUTH_USER_ID), "email": "client@example.com"},
        )

    settings = _settings()
    client = httpx.Client(
        base_url=settings.supabase_url,
        transport=httpx.MockTransport(handler),
    )
    admin = SupabaseAuthAdminClient(settings, client=client)

    assert (
        admin.create_user(
            email="Client@Example.com",
            password="Generated@Pass9",
        )
        == AUTH_USER_ID
    )


def test_update_user_password_puts_only_new_password_to_target_user() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PUT"
        assert request.url.path == f"/auth/v1/admin/users/{AUTH_USER_ID}"
        assert json.loads(request.content) == {"password": "Replacement#Pass8"}
        return httpx.Response(200, json={"id": str(AUTH_USER_ID)})

    settings = _settings()
    client = httpx.Client(
        base_url=settings.supabase_url,
        transport=httpx.MockTransport(handler),
    )
    admin = SupabaseAuthAdminClient(settings, client=client)

    admin.update_user_password(
        auth_user_id=AUTH_USER_ID,
        password="Replacement#Pass8",
    )
