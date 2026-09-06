from __future__ import annotations

import json

import httpx

from gilbic_backend.auth_client import SupabaseAuthClient
from gilbic_backend.config import Settings


def test_update_password_uses_authenticated_user_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PUT"
        assert request.url.path == "/auth/v1/user"
        assert request.headers["Authorization"] == "Bearer access-token"
        assert request.headers["apikey"] == "sb_publishable_test"
        assert json.loads(request.content) == {"password": "example-new-password-2"}
        return httpx.Response(200, json={"id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"})

    settings = Settings(
        database_url="postgresql://127.0.0.1:5432/test",
        supabase_url="https://project.supabase.co",
        supabase_publishable_key="sb_publishable_test",
    )
    http = httpx.Client(
        base_url=settings.supabase_url,
        transport=httpx.MockTransport(handler),
    )
    client = SupabaseAuthClient(settings, client=http)

    client.update_password(
        access_token="access-token",
        password="example-new-password-2",
    )
