from __future__ import annotations

import importlib
from copy import deepcopy
from types import SimpleNamespace
from uuid import UUID

import pytest


AUTH_ID = UUID("11111111-1111-4111-8111-111111111111")
ACTOR_ID = UUID("22222222-2222-4222-8222-222222222222")
CLIENT_ID = UUID("33333333-3333-4333-8333-333333333333")
CIF_ID = UUID("44444444-4444-4444-8444-444444444444")
PERMISSION = "client_onboarding.requirement.review"
URL = f"/api/v1/management/clients/{CLIENT_ID}/cif/draft-information"
HEADERS = {"Authorization": "Bearer synthetic-correction-token", "X-Device-Id": "office-correction"}
INFORMATION = {
    "full_name": "Synthetic CIF Borrower",
    "phone_number": "09170000000",
    "email": None,
    "present_address": "Synthetic office review address",
}
CORRECTED = {**INFORMATION, "phone_number": "09171111111"}
BODY = {
    "cif_version_id": str(CIF_ID),
    "expected_information": INFORMATION,
    "corrected_information": CORRECTED,
    "reason": "Applicant corrected a typing error during office review.",
}


class CorrectionRepository:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def correct_draft_information(self, **payload):
        self.calls.append(payload)
        if self.error == "conflict":
            module = importlib.import_module("gilbic_backend.client_cif_repository")
            raise module.ClientCifConflict("CIF changed; refresh the office review.")
        if self.error == "invalid":
            raise ValueError("Invalid CIF correction.")
        return SimpleNamespace(
            **payload["corrected_information"], id=CIF_ID, client_id=CLIENT_ID,
            version_number=1, status="draft", baseline_liveness_status="pending",
            national_id_egov_evidence_reference="PRIVATE-NATIONAL-REF",
            baseline_face_scan_evidence_reference="PRIVATE-FACE-REF",
        )


def _client(*, role="employee", permissions=(PERMISSION,), account_error=None, error=None):
    # Lazy imports allow discovery without pretending the application has run.
    from fastapi.testclient import TestClient
    from gilbic_backend.account_repository import AccountContext
    from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
    from gilbic_backend.auth_client import AuthSession
    from gilbic_backend.main import create_app

    class Auth:
        def get_user(self, *, access_token):
            assert access_token == "synthetic-correction-token"
            return AuthSession(
                auth_user_id=AUTH_ID, email="synthetic-office@example.com",
                access_token=access_token, refresh_token=None, expires_at=None,
                email_confirmed=True,
            )

    class Accounts:
        def get_context_for_device(self, *, auth_user_id, device_identifier):
            assert auth_user_id == AUTH_ID and device_identifier == "office-correction"
            if account_error:
                module = importlib.import_module("gilbic_backend.account_repository")
                raise getattr(module, account_error)("Synthetic access denial.")
            return AccountContext(
                user_id=ACTOR_ID, auth_user_id=AUTH_ID, username="synthetic.office",
                email="synthetic-office@example.com", full_name="Synthetic Office Actor",
                status="active", roles=(role,), permissions=permissions, device_registered=True,
            )

    module = importlib.import_module("gilbic_backend.client_cif_api")
    repository = CorrectionRepository(error=error)
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: Auth()
    app.dependency_overrides[account_repository_dependency] = lambda: Accounts()
    app.dependency_overrides[module.client_cif_repository_dependency] = lambda: repository
    return TestClient(app), repository


@pytest.mark.parametrize("role", ["employee", "management"])
def test_authorized_office_actor_can_correct_information_without_confirmation(role):
    client, repository = _client(role=role)
    response = client.patch(URL, headers=HEADERS, json=BODY)
    assert response.status_code == 200
    assert repository.calls == [{
        **BODY, "cif_version_id": CIF_ID, "actor_user_id": ACTOR_ID, "client_id": CLIENT_ID,
    }]
    assert response.json() == {
        **CORRECTED, "client_id": str(CLIENT_ID), "cif_version_id": str(CIF_ID),
        "version_number": 1, "status": "draft", "liveness_status": "pending",
        "review_scope": "cif_information_only",
    }
    assert "no-store" in response.headers.get("cache-control", "").lower()
    assert "PRIVATE-" not in response.text


@pytest.mark.parametrize("role", ["collector", "client"])
def test_non_office_role_cannot_correct_even_with_permission(role):
    client, repository = _client(role=role)
    assert client.patch(URL, headers=HEADERS, json=BODY).status_code == 403
    assert repository.calls == []


def test_correction_requires_existing_permission():
    client, repository = _client(permissions=())
    assert client.patch(URL, headers=HEADERS, json=BODY).status_code == 403
    assert repository.calls == []


@pytest.mark.parametrize("omitted,expected", [("Authorization", 401), ("X-Device-Id", 400)])
def test_correction_requires_authentication_and_active_device(omitted, expected):
    client, repository = _client()
    headers = {key: value for key, value in HEADERS.items() if key != omitted}
    assert client.patch(URL, headers=headers, json=BODY).status_code == expected
    assert repository.calls == []


@pytest.mark.parametrize("error", ["DeviceNotRegistered", "DeviceRevoked", "AccountDisabled"])
def test_correction_preserves_account_and_device_denials(error):
    client, repository = _client(account_error=error)
    assert client.patch(URL, headers=HEADERS, json=BODY).status_code == 403
    assert repository.calls == []


@pytest.mark.parametrize("scope,field,value", [
    ("body", "actor_user_id", str(AUTH_ID)),
    ("body", "client_id", str(AUTH_ID)),
    ("corrected_information", "status", "active"),
    ("corrected_information", "baseline_liveness_status", "passed"),
    ("expected_information", "national_id_egov_evidence_reference", "PRIVATE-FORGED"),
])
def test_correction_rejects_forged_actor_state_or_evidence(scope, field, value):
    client, repository = _client()
    body = deepcopy(BODY)
    target = body if scope == "body" else body[scope]
    target[field] = value
    assert client.patch(URL, headers=HEADERS, json=body).status_code == 422
    assert repository.calls == []


@pytest.mark.parametrize("field,value", [
    ("full_name", "   "), ("phone_number", "not-a-number"),
    ("present_address", "   "), ("email", "x" * 321),
])
def test_correction_rejects_invalid_new_information(field, value):
    client, repository = _client()
    body = deepcopy(BODY)
    body["corrected_information"][field] = value
    assert client.patch(URL, headers=HEADERS, json=body).status_code == 422
    assert repository.calls == []


@pytest.mark.parametrize("field", ["cif_version_id", "expected_information", "reason"])
def test_correction_requires_version_review_snapshot_and_reason(field):
    client, repository = _client()
    body = deepcopy(BODY)
    del body[field]
    assert client.patch(URL, headers=HEADERS, json=body).status_code == 422
    assert repository.calls == []


def test_blank_correction_reason_is_rejected():
    client, repository = _client()
    body = {**BODY, "reason": "   "}
    assert client.patch(URL, headers=HEADERS, json=body).status_code == 422
    assert repository.calls == []


def test_correction_normalizes_new_values_but_preserves_exact_reviewed_values():
    client, repository = _client()
    body = deepcopy(BODY)
    body["expected_information"]["full_name"] = "  Exact  stored name  "
    body["corrected_information"] = {
        "full_name": "  Synthetic   CIF Borrower ", "phone_number": "0917-111-1111",
        "email": "  REVIEW@EXAMPLE.COM ", "present_address": " Synthetic   office review address ",
    }
    response = client.patch(URL, headers=HEADERS, json=body)
    assert response.status_code == 200
    sent = repository.calls[0]
    assert sent["expected_information"] == body["expected_information"]
    assert sent["corrected_information"] == {**CORRECTED, "email": "review@example.com"}


@pytest.mark.parametrize("error,expected", [("conflict", 409), ("invalid", 400)])
def test_correction_preserves_repository_error_boundary(error, expected):
    client, repository = _client(error=error)
    assert client.patch(URL, headers=HEADERS, json=BODY).status_code == expected
    assert len(repository.calls) == 1


@pytest.mark.parametrize("surface", ["public", "client"])
def test_no_public_or_client_correction_alias(surface):
    client, repository = _client()
    response = client.patch(
        f"/api/v1/{surface}/clients/{CLIENT_ID}/cif/draft-information",
        headers=HEADERS, json=BODY,
    )
    assert response.status_code == 404
    assert repository.calls == []
