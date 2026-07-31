from __future__ import annotations

import json
from uuid import UUID

import httpx
import pytest

from gilbic_backend.auth_admin_client import SupabaseAuthAdminClient
from gilbic_backend.auth_client import SupabaseAuthError
from gilbic_backend.config import Settings


INVITED_ID = UUID("44444444-4444-4444-8444-444444444444")


def test_invite_uses_server_secret_and_redirect() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/auth/v1/invite"
        assert request.headers["apikey"] == "sb_secret_test"
        assert request.headers["authorization"] == "Bearer sb_secret_test"
        assert json.loads(request.content) == {
            "email": "collector@example.com",
            "redirect_to": "https://gilbic.example.com/set-password",
        }
        return httpx.Response(
            200,
            json={"id": str(INVITED_ID), "email": "collector@example.com"},
        )

    settings = Settings(
        supabase_url="https://project.supabase.co",
        supabase_publishable_key="sb_publishable_test",
        supabase_secret_key="sb_secret_test",
        staff_invite_redirect_url="https://gilbic.example.com/set-password",
    )
    client = httpx.Client(
        base_url=settings.supabase_url,
        transport=httpx.MockTransport(handler),
    )
    admin = SupabaseAuthAdminClient(settings, client=client)

    assert admin.invite_user(email="Collector@Example.com") == INVITED_ID


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
