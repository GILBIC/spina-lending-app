"""Provider outages must not become credential rejection or account activation."""

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from gilbic_backend.auth_api import (
    account_repository_dependency,
    auth_client_dependency,
    create_auth_router,
)
from gilbic_backend.auth_client import SupabaseAuthClient
from gilbic_backend.config import Settings
from test_auth_api import FakeAccounts


@pytest.mark.parametrize("operation", ["login", "refresh", "me"])
@pytest.mark.parametrize(
    "provider_status,expected_status",
    [
        (429, 429),
        (408, 503),
        (409, 503),
        (404, 502),
        (500, 503),
        (501, 503),
        (502, 503),
        (503, 503),
        (504, 503),
        (400, 401),
        (401, 401),
        (403, 401),
    ],
)
def test_provider_failures_preserve_retryable_status_and_never_load_account(
    operation, provider_status, expected_status
):
    accounts = FakeAccounts()
    app = FastAPI()
    app.include_router(create_auth_router())
    settings = Settings(
        _env_file=None,
        supabase_url="https://auth.invalid",
        supabase_publishable_key="synthetic-key",
    )
    with httpx.Client(
        base_url="https://auth.invalid",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                provider_status,
                json={"message": "provider-private-detail"},
            )
        ),
    ) as provider:
        auth = SupabaseAuthClient(settings, client=provider)
        app.dependency_overrides[auth_client_dependency] = lambda: auth
        app.dependency_overrides[account_repository_dependency] = lambda: accounts
        with TestClient(app) as client:
            headers = {
                "Authorization": "Bearer retained-token",
                "X-Device-Id": "test-device",
            }
            if operation == "me":
                response = client.get("/api/v1/auth/me", headers=headers)
            else:
                body = (
                    {"username": "collector.one", "password": "correct-password"}
                    if operation == "login"
                    else {"refresh_token": "refresh-token-12345"}
                )
                response = client.post(
                    "/api/v1/auth/" + operation, json=body, headers=headers
                )
    assert response.status_code == expected_status
    assert "provider-private-detail" not in response.text
    assert accounts.checked_device is None
    assert accounts.registered_device is None
