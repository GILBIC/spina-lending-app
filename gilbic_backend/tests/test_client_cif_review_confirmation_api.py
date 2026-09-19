from __future__ import annotations

import importlib
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest


AUTH_ID = UUID("11111111-1111-4111-8111-111111111111")
ACTOR_ID = UUID("22222222-2222-4222-8222-222222222222")
CLIENT_ID = UUID("33333333-3333-4333-8333-333333333333")
CIF_ID = UUID("44444444-4444-4444-8444-444444444444")
CONFIRMATION_ID = UUID("55555555-5555-4555-8555-555555555555")
PERMISSION = "client_onboarding.requirement.review"
URL = f"/api/v1/management/clients/{CLIENT_ID}/cif/review-confirmations"
ROUTE_PATH = "/api/v1/management/clients/{client_id}/cif/review-confirmations"
HEADERS = {
    "Authorization": "Bearer synthetic-cif-confirmation-token",
    "X-Device-Id": "office-cif-confirmation",
}
INFORMATION = {
    "full_name": "  Exact  Borrower Name  ",
    "phone_number": "0917-111-1111",
    "email": " Mixed.Case@Example.COM ",
    "present_address": "  Exact   reviewed address  ",
}
CONFIRMED_AT = datetime(
    2026, 9, 18, 15, 6, 7, tzinfo=timezone(timedelta(hours=8))
)


def _body() -> dict[str, object]:
    return {
        "cif_version_id": str(CIF_ID),
        "expected_information": deepcopy(INFORMATION),
        "applicant_confirmation_evidence_reference": "  SYNTHETIC-CIF-ACK  ",
    }


class ConfirmationRepository:
    def __init__(self, error: str | None = None):
        self.error = error
        self.calls: list[dict[str, object]] = []

    def confirm_review(self, **payload):
        self.calls.append(payload)
        module = importlib.import_module("gilbic_backend.client_cif_repository")
        if self.error == "invalid":
            raise ValueError("Applicant confirmation evidence reference is required.")
        if self.error == "access":
            raise module.ClientCifAccessDenied(
                "An active authorized office account is required."
            )
        conflicts = {
            "stale": "CIF changed; refresh the office review.",
            "ineligible": "No eligible current CIF is available.",
            "conflicting_retry": (
                "CIF version was already confirmed with different review evidence or witness."
            ),
        }
        if self.error in conflicts:
            raise module.ClientCifConflict(conflicts[self.error])
        return SimpleNamespace(
            id=CONFIRMATION_ID,
            client_id=payload["client_id"],
            cif_version_id=payload["cif_version_id"],
            review_cycle_number=7,
            review_snapshot=payload["expected_information"],
            applicant_confirmation_evidence_reference=payload[
                "applicant_confirmation_evidence_reference"
            ],
            witnessed_by_user_id=ACTOR_ID,
            confirmed_at=CONFIRMED_AT,
            private_evidence_reference="PRIVATE-EVIDENCE",
            activation_status="active",
            approval_status="approved",
            release_status="released",
        )


def _client(
    *,
    role: str = "employee",
    permissions: tuple[str, ...] = (PERMISSION,),
    repository_error: str | None = None,
    account_error: str | None = None,
):
    from fastapi.testclient import TestClient
    from gilbic_backend.account_repository import AccountContext
    from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
    from gilbic_backend.auth_client import AuthSession
    from gilbic_backend.main import create_app

    module = importlib.import_module("gilbic_backend.client_cif_api")

    class Auth:
        def get_user(self, *, access_token):
            assert access_token == "synthetic-cif-confirmation-token"
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
            assert device_identifier == "office-cif-confirmation"
            if account_error:
                account_module = importlib.import_module(
                    "gilbic_backend.account_repository"
                )
                raise getattr(account_module, account_error)("Synthetic access denial.")
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

    repository = ConfirmationRepository(repository_error)
    app = create_app()
    if "post" not in app.openapi().get("paths", {}).get(ROUTE_PATH, {}):
        pytest.fail("CIF review confirmation API is not implemented")
    app.dependency_overrides[auth_client_dependency] = lambda: Auth()
    app.dependency_overrides[account_repository_dependency] = lambda: Accounts()
    app.dependency_overrides[module.client_cif_repository_dependency] = lambda: repository
    return TestClient(app), repository


@pytest.mark.parametrize("role", ["employee", "management"])
def test_office_actor_records_exact_cif_review_confirmation(role: str) -> None:
    client, repository = _client(role=role)

    response = client.post(URL, headers=HEADERS, json=_body())

    assert response.status_code == 201
    assert response.json() == {
        "review_confirmation_id": str(CONFIRMATION_ID),
        "client_id": str(CLIENT_ID),
        "cif_version_id": str(CIF_ID),
        "review_cycle_number": 7,
        "witnessed_by_user_id": str(ACTOR_ID),
        "confirmed_at": "2026-09-18T07:06:07Z",
        "review_scope": "cif_information_only",
    }
    assert "no-store" in response.headers.get("cache-control", "").lower()
    assert "SYNTHETIC-CIF-ACK" not in response.text
    assert "Exact  Borrower" not in response.text
    assert "PRIVATE-EVIDENCE" not in response.text
    assert "approved" not in response.text and "released" not in response.text
    assert repository.calls == [{
        "actor_user_id": ACTOR_ID,
        "client_id": CLIENT_ID,
        "cif_version_id": CIF_ID,
        "expected_information": INFORMATION,
        "applicant_confirmation_evidence_reference": "SYNTHETIC-CIF-ACK",
    }]


def test_exact_retry_delegates_each_time_and_preserves_saved_response() -> None:
    client, repository = _client()
    first = client.post(URL, headers=HEADERS, json=_body())
    repeated = client.post(URL, headers=HEADERS, json=_body())
    assert first.status_code == repeated.status_code == 201
    assert first.json() == repeated.json()
    assert len(repository.calls) == 2
    assert repository.calls[0] == repository.calls[1]


@pytest.mark.parametrize("role", ["collector", "client"])
def test_non_office_role_is_denied_even_with_permission(role: str) -> None:
    client, repository = _client(role=role)
    assert client.post(URL, headers=HEADERS, json=_body()).status_code == 403
    assert repository.calls == []


def test_confirmation_requires_permission() -> None:
    client, repository = _client(permissions=())
    assert client.post(URL, headers=HEADERS, json=_body()).status_code == 403
    assert repository.calls == []


@pytest.mark.parametrize("omitted,status", [("Authorization", 401), ("X-Device-Id", 400)])
def test_confirmation_requires_authentication_and_device(omitted: str, status: int) -> None:
    client, repository = _client()
    headers = {key: value for key, value in HEADERS.items() if key != omitted}
    assert client.post(URL, headers=headers, json=_body()).status_code == status
    assert repository.calls == []


@pytest.mark.parametrize("error", ["DeviceNotRegistered", "DeviceRevoked", "AccountDisabled"])
def test_confirmation_preserves_account_denials(error: str) -> None:
    client, repository = _client(account_error=error)
    response = client.post(URL, headers=HEADERS, json=_body())
    assert response.status_code == 403
    assert response.json() == {"detail": "Synthetic access denial."}
    assert repository.calls == []


@pytest.mark.parametrize(
    "error,status,detail",
    [
        ("invalid", 400, "Applicant confirmation evidence reference is required."),
        ("access", 403, "An active authorized office account is required."),
        ("stale", 409, "CIF changed; refresh the office review."),
        ("ineligible", 409, "No eligible current CIF is available."),
        (
            "conflicting_retry",
            409,
            "CIF version was already confirmed with different review evidence or witness.",
        ),
    ],
)
def test_repository_errors_preserve_http_boundary(error: str, status: int, detail: str) -> None:
    client, repository = _client(repository_error=error)
    response = client.post(URL, headers=HEADERS, json=_body())
    assert response.status_code == status
    assert response.json() == {"detail": detail}
    assert len(repository.calls) == 1


@pytest.mark.parametrize(
    "field",
    ["cif_version_id", "expected_information", "applicant_confirmation_evidence_reference"],
)
def test_required_body_field_is_rejected_before_repository(field: str) -> None:
    client, repository = _client()
    body = _body()
    del body[field]
    assert client.post(URL, headers=HEADERS, json=body).status_code == 422
    assert repository.calls == []


@pytest.mark.parametrize("reference", ["", "   ", None, 123])
def test_evidence_reference_must_be_nonblank_text(reference: object) -> None:
    client, repository = _client()
    body = {**_body(), "applicant_confirmation_evidence_reference": reference}
    assert client.post(URL, headers=HEADERS, json=body).status_code == 422
    assert repository.calls == []


@pytest.mark.parametrize("coordinate", ["client_id", "cif_version_id"])
def test_malformed_identity_is_rejected_before_repository(coordinate: str) -> None:
    client, repository = _client()
    url, body = URL, _body()
    if coordinate == "client_id":
        url = URL.replace(str(CLIENT_ID), "not-a-uuid")
    else:
        body["cif_version_id"] = "not-a-uuid"
    assert client.post(url, headers=HEADERS, json=body).status_code == 422
    assert repository.calls == []


@pytest.mark.parametrize(
    "mutation",
    [
        "missing", "extra", "full_name_number", "phone_number_number",
        "email_number", "present_address_number", "email_null",
    ],
)
def test_review_snapshot_has_exact_four_field_raw_shape(mutation: str) -> None:
    client, repository = _client()
    body = _body()
    information = body["expected_information"]
    if mutation == "missing":
        del information["present_address"]
    elif mutation == "extra":
        information["status"] = "active"
    elif mutation == "full_name_number":
        information["full_name"] = 42
    elif mutation == "phone_number_number":
        information["phone_number"] = 42
    elif mutation == "email_number":
        information["email"] = 42
    elif mutation == "present_address_number":
        information["present_address"] = 42
    else:
        information["email"] = None
        response = client.post(URL, headers=HEADERS, json=body)
        assert response.status_code == 201
        assert repository.calls[0]["expected_information"]["email"] is None
        return
    assert client.post(URL, headers=HEADERS, json=body).status_code == 422
    assert repository.calls == []


@pytest.mark.parametrize(
    "field",
    [
        "actor_user_id", "client_id", "review_cycle_number", "witnessed_by_user_id",
        "confirmed_at", "activation_status", "approval_status", "release_status",
    ],
)
def test_authoritative_extra_field_is_rejected(field: str) -> None:
    client, repository = _client()
    body = {**_body(), field: "caller-controlled"}
    assert client.post(URL, headers=HEADERS, json=body).status_code == 422
    assert repository.calls == []


@pytest.mark.parametrize("method", ["GET", "PATCH", "DELETE"])
def test_confirmation_collection_exposes_only_post(method: str) -> None:
    client, repository = _client()
    assert client.request(method, URL, headers=HEADERS).status_code == 405
    assert repository.calls == []


@pytest.mark.parametrize("surface", ["public", "client"])
def test_no_public_or_client_alias(surface: str) -> None:
    client, repository = _client()
    alias = URL.replace("/api/v1/management/", f"/api/v1/{surface}/")
    assert client.post(alias, headers=HEADERS, json=_body()).status_code == 404
    assert repository.calls == []
