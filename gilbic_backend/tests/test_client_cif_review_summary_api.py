from __future__ import annotations

import importlib
from types import SimpleNamespace
from uuid import UUID

import pytest


AUTH_ID = UUID("11111111-1111-4111-8111-111111111111")
ACTOR_ID = UUID("22222222-2222-4222-8222-222222222222")
CLIENT_ID = UUID("33333333-3333-4333-8333-333333333333")
CIF_ID = UUID("44444444-4444-4444-8444-444444444444")
PERMISSION = "client_onboarding.requirement.review"
URL = f"/api/v1/management/clients/{CLIENT_ID}/cif/review-summary"
HEADERS = {
    "Authorization": "Bearer synthetic-review-token",
    "X-Device-Id": "office-review",
}


class SummaryRepository:
    def __init__(self, *, cif_status="draft", conflict=False):
        self.calls: list[UUID] = []
        self.cif_status = cif_status
        self.conflict = conflict

    def get_review_summary(self, *, client_id: UUID):
        self.calls.append(client_id)
        if self.conflict:
            module = importlib.import_module("gilbic_backend.client_cif_repository")
            raise module.ClientCifConflict("No eligible current CIF is available.")
        # Sentinel private fields must never be copied into the review response.
        return SimpleNamespace(
            id=CIF_ID,
            client_id=CLIENT_ID,
            version_number=1,
            status=self.cif_status,
            full_name="Synthetic CIF Borrower",
            phone_number="09170000000",
            email=None,
            present_address="Synthetic office review address",
            baseline_liveness_status=(
                "passed" if self.cif_status == "active" else "pending"
            ),
            national_id_egov_evidence_reference="PRIVATE-NATIONAL-ID-REF",
            tin_id_egov_evidence_reference="PRIVATE-TIN-REF",
            meralco_bill_evidence_reference="PRIVATE-RESIDENCE-REF",
            baseline_face_scan_evidence_reference="PRIVATE-FACE-REF",
        )


def _client(*, role="employee", permissions=(PERMISSION,), account_error=None, **kwargs):
    # Lazy imports keep test discovery separate from application initialization.
    from fastapi.testclient import TestClient
    from gilbic_backend.account_repository import AccountContext
    from gilbic_backend.auth_api import (
        account_repository_dependency,
        auth_client_dependency,
    )
    from gilbic_backend.auth_client import AuthSession
    from gilbic_backend.main import create_app

    class Auth:
        def get_user(self, *, access_token):
            assert access_token == "synthetic-review-token"
            return AuthSession(
                auth_user_id=AUTH_ID,
                email="synthetic-office@example.com",
                access_token=access_token,
                refresh_token=None,
                expires_at=None,
                email_confirmed=True,
            )

    class Accounts:
        def get_context_for_device(self, *, auth_user_id, device_identifier):
            assert auth_user_id == AUTH_ID
            assert device_identifier == "office-review"
            if account_error:
                module = importlib.import_module("gilbic_backend.account_repository")
                raise getattr(module, account_error)("Synthetic access denial.")
            return AccountContext(
                user_id=ACTOR_ID,
                auth_user_id=AUTH_ID,
                username="synthetic.office",
                email="synthetic-office@example.com",
                full_name="Synthetic Office Actor",
                status="active",
                roles=(role,),
                permissions=permissions,
                device_registered=True,
            )

    module = importlib.import_module("gilbic_backend.client_cif_api")
    repository = SummaryRepository(**kwargs)
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: Auth()
    app.dependency_overrides[account_repository_dependency] = lambda: Accounts()
    app.dependency_overrides[module.client_cif_repository_dependency] = lambda: repository
    return TestClient(app), repository


@pytest.mark.parametrize("role", ["employee", "management"])
@pytest.mark.parametrize("cif_status", ["draft", "active"])
def test_office_review_returns_only_cif_information_with_exact_version(
    role: str, cif_status: str
) -> None:
    client, repository = _client(role=role, cif_status=cif_status)

    response = client.get(URL, headers=HEADERS)

    assert response.status_code == 200
    assert response.json() == {
        "client_id": str(CLIENT_ID),
        "cif_version_id": str(CIF_ID),
        "version_number": 1,
        "status": cif_status,
        "full_name": "Synthetic CIF Borrower",
        "phone_number": "09170000000",
        "email": None,
        "present_address": "Synthetic office review address",
        "liveness_status": "passed" if cif_status == "active" else "pending",
        "review_scope": "cif_information_only",
    }
    assert "no-store" in response.headers.get("cache-control", "").lower()
    assert "PRIVATE-" not in response.text
    assert repository.calls == [CLIENT_ID]


@pytest.mark.parametrize("role", ["collector", "client"])
def test_non_office_role_cannot_read_review_even_with_permission(role: str) -> None:
    client, repository = _client(role=role)
    response = client.get(URL, headers=HEADERS)
    assert response.status_code == 403
    assert repository.calls == []


def test_office_review_requires_existing_review_permission() -> None:
    client, repository = _client(permissions=())
    response = client.get(URL, headers=HEADERS)
    assert response.status_code == 403
    assert repository.calls == []


@pytest.mark.parametrize("omitted,expected", [("Authorization", 401), ("X-Device-Id", 400)])
def test_office_review_requires_authentication_and_device(
    omitted: str, expected: int
) -> None:
    client, repository = _client()
    headers = {key: value for key, value in HEADERS.items() if key != omitted}
    response = client.get(URL, headers=headers)
    assert response.status_code == expected
    assert repository.calls == []


@pytest.mark.parametrize("error", ["DeviceNotRegistered", "DeviceRevoked", "AccountDisabled"])
def test_office_review_preserves_account_and_device_denials(error: str) -> None:
    client, repository = _client(account_error=error)
    response = client.get(URL, headers=HEADERS)
    assert response.status_code == 403
    assert repository.calls == []


def test_missing_eligible_cif_returns_conflict_without_starting_draft() -> None:
    client, repository = _client(conflict=True)
    response = client.get(URL, headers=HEADERS)
    assert response.status_code == 409
    assert response.json() == {"detail": "No eligible current CIF is available."}
    assert repository.calls == [CLIENT_ID]


@pytest.mark.parametrize("method", ["POST", "PATCH"])
def test_review_summary_is_not_a_confirmation_or_mutation_endpoint(method: str) -> None:
    client, repository = _client()
    response = client.request(method, URL, headers=HEADERS, json={})
    assert response.status_code == 405
    assert repository.calls == []


@pytest.mark.parametrize("surface", ["public", "client"])
def test_no_public_or_client_self_service_review_alias(surface: str) -> None:
    client, repository = _client()
    response = client.get(
        f"/api/v1/{surface}/clients/{CLIENT_ID}/cif/review-summary", headers=HEADERS
    )
    assert response.status_code == 404
    assert repository.calls == []
