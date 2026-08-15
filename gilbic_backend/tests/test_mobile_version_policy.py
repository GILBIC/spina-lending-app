from __future__ import annotations

from fastapi.testclient import TestClient

from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.config import Settings, get_settings
from gilbic_backend.main import create_app
from gilbic_backend.mobile_version_policy import (
    UnsupportedMobileAppVersion,
    enforce_mobile_app_version,
    parse_mobile_version,
)


class _UnexpectedAuth:
    def sign_in(self, **kwargs):  # pragma: no cover - must not be reached
        raise AssertionError(f"auth should not be reached: {kwargs}")

    def get_user(self, **kwargs):  # pragma: no cover - must not be reached
        raise AssertionError(f"auth should not be reached: {kwargs}")


class _UnexpectedAccounts:
    def resolve_email(self, identifier: str):  # pragma: no cover - must not be reached
        raise AssertionError(f"accounts should not be reached: {identifier}")


def _client(*, android: str = "", ios: str = "") -> TestClient:
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: _UnexpectedAuth()
    app.dependency_overrides[account_repository_dependency] = lambda: _UnexpectedAccounts()
    app.dependency_overrides[get_settings] = lambda: Settings(
        mobile_android_minimum_version=android,
        mobile_ios_minimum_version=ios,
    )
    return TestClient(app)


def test_version_comparison_honors_release_and_build_number() -> None:
    assert parse_mobile_version("0.4.0+4") > parse_mobile_version("0.4.0+3")
    assert parse_mobile_version("0.4.1+1") > parse_mobile_version("0.4.0+999")
    assert parse_mobile_version("1.0") == parse_mobile_version("1.0.0+0")


def test_configured_policy_rejects_unverifiable_mobile_build() -> None:
    settings = Settings(mobile_android_minimum_version="0.4.0+4")

    try:
        enforce_mobile_app_version(
            platform=None,
            app_version=None,
            settings=settings,
        )
    except UnsupportedMobileAppVersion as exc:
        assert "cannot be verified" in str(exc)
    else:  # pragma: no cover - policy must fail closed
        raise AssertionError("configured mobile policy accepted missing metadata")


def test_mobile_login_rejects_outdated_android_before_authentication() -> None:
    client = _client(android="0.4.0+4")

    response = client.post(
        "/api/mobile/v1/auth/login",
        json={
            "username": "collector.one",
            "password": "secret",
            "device_id": "install-1",
            "platform": "android",
            "app_version": "0.4.0+3",
        },
    )

    assert response.status_code == 426
    assert response.json()["detail"] == (
        "This Gilbic Android version is no longer supported. "
        "Update to version 0.4.0+4 or later before continuing."
    )


def test_mobile_login_cannot_bypass_configured_policy_by_omitting_platform() -> None:
    client = _client(android="0.4.0+4")

    response = client.post(
        "/api/mobile/v1/auth/login",
        json={"username": "collector.one", "password": "secret"},
    )

    assert response.status_code == 426
    assert "cannot be verified" in response.json()["detail"]


def test_active_ios_session_is_blocked_before_device_auth_when_build_is_old() -> None:
    client = _client(ios="1.2.0+12")

    response = client.get(
        "/api/mobile/v1/auth/me",
        headers={
            "Authorization": "Bearer access-token",
            "X-Device-Id": "install-ios",
            "X-App-Platform": "ios",
            "X-App-Version": "1.2.0+11",
        },
    )

    assert response.status_code == 426
    assert response.json()["detail"] == (
        "This Gilbic iOS version is no longer supported. "
        "Update to version 1.2.0+12 or later before continuing."
    )


def test_unconfigured_policy_keeps_existing_development_behavior() -> None:
    settings = Settings()
    enforce_mobile_app_version(
        platform=None,
        app_version=None,
        settings=settings,
    )
