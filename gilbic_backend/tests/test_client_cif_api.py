from __future__ import annotations

import importlib
from datetime import datetime, timezone
from types import ModuleType, SimpleNamespace
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.main import create_app


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
ACTOR_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
CLIENT_ID = UUID("33333333-3333-4333-8333-333333333333")
DEVICE_ID = "office-cif-device"
PERMISSION = "client_onboarding.requirement.review"


class FakeAuthClient:
    def get_user(self, *, access_token: str) -> AuthSession:
        assert access_token == "office-cif-token"
        return AuthSession(
            auth_user_id=AUTH_USER_ID,
            email="actor@example.com",
            access_token=access_token,
            refresh_token=None,
            expires_at=None,
            email_confirmed=True,
        )


class FakeAccounts:
    def __init__(self, context: AccountContext) -> None:
        self.context = context

    def get_context_for_device(
        self,
        *,
        auth_user_id: UUID,
        device_identifier: str | None,
    ) -> AccountContext:
        assert auth_user_id == AUTH_USER_ID
        assert device_identifier == DEVICE_ID
        return self.context


class FakeCifRepository:
    def __init__(self) -> None:
        self.begin_payload: dict[str, Any] | None = None
        self.face_payload: dict[str, Any] | None = None
        self.activate_payload: dict[str, Any] | None = None

    def begin_draft(self, **payload: Any):
        self.begin_payload = payload
        return SimpleNamespace(
            client_id=CLIENT_ID,
            version_number=1,
            status="draft",
            baseline_liveness_status="pending",
            activated_at=None,
            expires_at=None,
            review_due_at=None,
        )

    def record_baseline_live_face(self, **payload: Any):
        self.face_payload = payload
        return SimpleNamespace(
            client_id=CLIENT_ID,
            version_number=1,
            status="draft",
            baseline_liveness_status="passed",
            activated_at=None,
            expires_at=None,
            review_due_at=None,
        )

    def activate_current(self, **payload: Any):
        self.activate_payload = payload
        return SimpleNamespace(
            client_id=CLIENT_ID,
            version_number=1,
            status="active",
            baseline_liveness_status="passed",
            activated_at=datetime(2026, 9, 11, 1, 0, tzinfo=timezone.utc),
            expires_at=datetime(2031, 9, 11, 1, 0, tzinfo=timezone.utc),
            review_due_at=datetime(2031, 6, 13, 1, 0, tzinfo=timezone.utc),
        )


def _load_cif_api_module() -> ModuleType:
    return importlib.import_module("gilbic_backend.client_cif_api")


def _actor_context(*, role: str, permissions: tuple[str, ...]) -> AccountContext:
    return AccountContext(
        user_id=ACTOR_USER_ID,
        auth_user_id=AUTH_USER_ID,
        username=f"{role}.one",
        email=f"{role}@example.com",
        full_name=f"{role.title()} One",
        status="active",
        roles=(role,),
        permissions=permissions,
        device_registered=True,
    )


def _client_for(
    *,
    role: str,
    permissions: tuple[str, ...],
) -> tuple[TestClient, FakeCifRepository]:
    module = _load_cif_api_module()
    repository = FakeCifRepository()
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts(
        _actor_context(role=role, permissions=permissions)
    )
    app.dependency_overrides[module.client_cif_repository_dependency] = lambda: repository
    return TestClient(app), repository


def _headers(*, include_device: bool = True) -> dict[str, str]:
    headers = {"Authorization": "Bearer office-cif-token"}
    if include_device:
        headers["X-Device-Id"] = DEVICE_ID
    return headers


def test_employee_with_permission_can_begin_cif_draft() -> None:
    client, repository = _client_for(role="employee", permissions=(PERMISSION,))

    response = client.post(
        f"/api/v1/management/clients/{CLIENT_ID}/cif/draft",
        headers=_headers(),
    )

    assert response.status_code == 201
    assert response.json() == {
        "client_id": str(CLIENT_ID),
        "version_number": 1,
        "status": "draft",
        "liveness_status": "pending",
    }
    assert repository.begin_payload == {
        "actor_user_id": ACTOR_USER_ID,
        "client_id": CLIENT_ID,
    }


def test_employee_with_permission_can_record_baseline_live_face() -> None:
    client, repository = _client_for(role="employee", permissions=(PERMISSION,))

    response = client.patch(
        f"/api/v1/management/clients/{CLIENT_ID}/cif/baseline-live-face",
        headers=_headers(),
        json={
            "evidence_reference": "FAKE-CONTROLLED-FACE-REF",
            "liveness_status": "passed",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "client_id": str(CLIENT_ID),
        "version_number": 1,
        "status": "draft",
        "liveness_status": "passed",
    }
    assert repository.face_payload == {
        "client_id": CLIENT_ID,
        "evidence_reference": "FAKE-CONTROLLED-FACE-REF",
        "liveness_status": "passed",
    }


def test_management_with_permission_can_activate_ready_cif() -> None:
    client, repository = _client_for(role="management", permissions=(PERMISSION,))

    response = client.post(
        f"/api/v1/management/clients/{CLIENT_ID}/cif/activate",
        headers=_headers(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["client_id"] == str(CLIENT_ID)
    assert payload["version_number"] == 1
    assert payload["status"] == "active"
    assert payload["activated_at"] == "2026-09-11T01:00:00Z"
    assert payload["expires_at"] == "2031-09-11T01:00:00Z"
    assert payload["review_due_at"] == "2031-06-13T01:00:00Z"
    assert repository.activate_payload == {
        "actor_user_id": ACTOR_USER_ID,
        "client_id": CLIENT_ID,
    }


@pytest.mark.parametrize("role", ["collector", "client"])
def test_non_office_roles_cannot_own_cif_even_if_permission_is_granted(role: str) -> None:
    client, repository = _client_for(role=role, permissions=(PERMISSION,))

    response = client.post(
        f"/api/v1/management/clients/{CLIENT_ID}/cif/draft",
        headers=_headers(),
    )

    assert response.status_code == 403
    assert repository.begin_payload is None


def test_cif_actions_require_existing_review_permission() -> None:
    client, repository = _client_for(role="employee", permissions=())

    response = client.post(
        f"/api/v1/management/clients/{CLIENT_ID}/cif/draft",
        headers=_headers(),
    )

    assert response.status_code == 403
    assert repository.begin_payload is None


def test_cif_actions_require_active_device_context() -> None:
    client, repository = _client_for(role="employee", permissions=(PERMISSION,))

    response = client.post(
        f"/api/v1/management/clients/{CLIENT_ID}/cif/draft",
        headers=_headers(include_device=False),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "X-Device-Id is required."
    assert repository.begin_payload is None
