from __future__ import annotations

import importlib
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest


AUTH_ID = UUID("11111111-1111-4111-8111-111111111111")
ACTOR_ID = UUID("22222222-2222-4222-8222-222222222222")
CLIENT_ID = UUID("33333333-3333-4333-8333-333333333333")
APPLICATION_ID = UUID("44444444-4444-4444-8444-444444444444")
VERSION_ID = UUID("55555555-5555-4555-8555-555555555555")
CIF_ID = UUID("66666666-6666-4666-8666-666666666666")
CONFIRMATION_ID = UUID("77777777-7777-4777-8777-777777777777")
PERMISSION = "client_onboarding.requirement.review"
URL = (
    f"/api/v1/management/clients/{CLIENT_ID}/loan-applications/"
    f"{APPLICATION_ID}/review-confirmations"
)
ROUTE_PATH = (
    "/api/v1/management/clients/{client_id}/loan-applications/"
    "{application_id}/review-confirmations"
)
HEADERS = {
    "Authorization": "Bearer synthetic-application-confirmation-token",
    "X-Device-Id": "office-application-confirmation",
}
CONFIRMED_AT = datetime(
    2026, 9, 18, 9, 4, 5, tzinfo=timezone(timedelta(hours=8))
)


def _body() -> dict[str, object]:
    return {
        "application_version_id": str(VERSION_ID),
        "applicant_confirmation_evidence_reference": "  SYNTHETIC-APPLICANT-ACK  ",
    }


class ConfirmationRepository:
    def __init__(self, *, error: str | None = None):
        self.calls: list[dict[str, object]] = []
        self.error = error

    def confirm_review(self, **payload):
        self.calls.append(payload)
        module = importlib.import_module("gilbic_backend.loan_application_repository")
        conflicts = {
            "stale_version": "Only the latest application version can be confirmed.",
            "different_evidence": (
                "Application version was already confirmed with different evidence or witness."
            ),
            "incomplete": "Application information is incomplete and cannot be confirmed.",
            "missing_cif_confirmation": (
                "CIF review confirmation is required before confirming the application."
            ),
            "stale_cif": (
                "No eligible current CIF is available for this application draft."
            ),
        }
        if self.error in conflicts:
            raise module.LoanApplicationConflict(conflicts[self.error])
        if self.error == "access":
            raise module.LoanApplicationAccessDenied(
                "An active authorized office account is required."
            )
        return SimpleNamespace(
            id=CONFIRMATION_ID,
            application_version_id=payload["application_version_id"],
            application_id=payload["application_id"],
            client_id=payload["client_id"],
            cif_version_id=CIF_ID,
            applicant_confirmation_evidence_reference=payload[
                "applicant_confirmation_evidence_reference"
            ],
            witnessed_by_user_id=ACTOR_ID,
            confirmed_at=CONFIRMED_AT,
            private_evidence_payload="PRIVATE-EVIDENCE",
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
    from gilbic_backend.auth_api import (
        account_repository_dependency,
        auth_client_dependency,
    )
    from gilbic_backend.auth_client import AuthSession
    from gilbic_backend.main import create_app

    module = importlib.import_module("gilbic_backend.loan_application_api")

    class Auth:
        def get_user(self, *, access_token):
            assert access_token == "synthetic-application-confirmation-token"
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
            assert device_identifier == "office-application-confirmation"
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

    repository = ConfirmationRepository(error=repository_error)
    app = create_app()
    if "post" not in app.openapi().get("paths", {}).get(ROUTE_PATH, {}):
        pytest.fail("Loan application review confirmation API is not implemented")
    app.dependency_overrides[auth_client_dependency] = lambda: Auth()
    app.dependency_overrides[account_repository_dependency] = lambda: Accounts()
    app.dependency_overrides[
        module.loan_application_repository_dependency
    ] = lambda: repository
    return TestClient(app), repository


@pytest.mark.parametrize("role", ["employee", "management"])
def test_office_actor_records_exact_application_review_confirmation(role: str) -> None:
    client, repository = _client(role=role)

    response = client.post(URL, headers=HEADERS, json=_body())

    assert response.status_code == 201
    assert response.json() == {
        "review_confirmation_id": str(CONFIRMATION_ID),
        "client_id": str(CLIENT_ID),
        "application_id": str(APPLICATION_ID),
        "application_version_id": str(VERSION_ID),
        "cif_version_id": str(CIF_ID),
        "witnessed_by_user_id": str(ACTOR_ID),
        "confirmed_at": "2026-09-18T01:04:05Z",
        "review_scope": "loan_application_information_only",
    }
    assert "no-store" in response.headers.get("cache-control", "").lower()
    assert "SYNTHETIC-APPLICANT-ACK" not in response.text
    assert "PRIVATE-EVIDENCE" not in response.text
    assert "approved" not in response.text and "released" not in response.text
    assert repository.calls == [
        {
            "actor_user_id": ACTOR_ID,
            "client_id": CLIENT_ID,
            "application_id": APPLICATION_ID,
            "application_version_id": VERSION_ID,
            "applicant_confirmation_evidence_reference": "SYNTHETIC-APPLICANT-ACK",
        }
    ]


def test_exact_retry_delegates_each_time_and_preserves_confirmation() -> None:
    client, repository = _client()
    body = _body()

    first = client.post(URL, headers=HEADERS, json=body)
    repeated = client.post(URL, headers=HEADERS, json=body)

    assert first.status_code == repeated.status_code == 201
    assert first.json() == repeated.json()
    assert first.json()["review_confirmation_id"] == str(CONFIRMATION_ID)
    assert first.json()["confirmed_at"] == "2026-09-18T01:04:05Z"
    assert len(repository.calls) == 2
    assert repository.calls[0] == repository.calls[1]


@pytest.mark.parametrize("role", ["collector", "client"])
def test_non_office_role_cannot_confirm_even_with_permission(role: str) -> None:
    client, repository = _client(role=role)
    assert client.post(URL, headers=HEADERS, json=_body()).status_code == 403
    assert repository.calls == []


def test_confirmation_requires_permission() -> None:
    client, repository = _client(permissions=())
    assert client.post(URL, headers=HEADERS, json=_body()).status_code == 403
    assert repository.calls == []


@pytest.mark.parametrize("omitted,expected", [("Authorization", 401), ("X-Device-Id", 400)])
def test_confirmation_requires_authentication_and_device(
    omitted: str, expected: int
) -> None:
    client, repository = _client()
    headers = {key: value for key, value in HEADERS.items() if key != omitted}
    assert client.post(URL, headers=headers, json=_body()).status_code == expected
    assert repository.calls == []


@pytest.mark.parametrize(
    "error", ["DeviceNotRegistered", "DeviceRevoked", "AccountDisabled"]
)
def test_confirmation_preserves_account_and_device_denials(error: str) -> None:
    client, repository = _client(account_error=error)
    response = client.post(URL, headers=HEADERS, json=_body())
    assert response.status_code == 403
    assert response.json() == {"detail": "Synthetic access denial."}
    assert repository.calls == []


@pytest.mark.parametrize(
    "error,expected_status,expected_detail",
    [
        ("access", 403, "An active authorized office account is required."),
        ("stale_version", 409, "Only the latest application version can be confirmed."),
        (
            "different_evidence",
            409,
            "Application version was already confirmed with different evidence or witness.",
        ),
        (
            "incomplete",
            409,
            "Application information is incomplete and cannot be confirmed.",
        ),
        (
            "missing_cif_confirmation",
            409,
            "CIF review confirmation is required before confirming the application.",
        ),
        (
            "stale_cif",
            409,
            "No eligible current CIF is available for this application draft.",
        ),
    ],
)
def test_confirmation_maps_repository_denials(
    error: str, expected_status: int, expected_detail: str
) -> None:
    client, repository = _client(repository_error=error)
    response = client.post(URL, headers=HEADERS, json=_body())
    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}
    assert len(repository.calls) == 1


@pytest.mark.parametrize(
    "field",
    ["application_version_id", "applicant_confirmation_evidence_reference"],
)
def test_required_confirmation_field_is_rejected_before_repository(field: str) -> None:
    client, repository = _client()
    body = _body()
    del body[field]
    assert client.post(URL, headers=HEADERS, json=body).status_code == 422
    assert repository.calls == []


@pytest.mark.parametrize("reference", ["", "   ", 123, None])
def test_confirmation_reference_must_be_nonblank_text(reference: object) -> None:
    client, repository = _client()
    body = {**_body(), "applicant_confirmation_evidence_reference": reference}
    assert client.post(URL, headers=HEADERS, json=body).status_code == 422
    assert repository.calls == []


@pytest.mark.parametrize(
    "coordinate", ["client_id", "application_id", "application_version_id"]
)
def test_malformed_confirmation_identity_is_rejected_before_repository(
    coordinate: str,
) -> None:
    client, repository = _client()
    url = URL
    body = _body()
    if coordinate == "client_id":
        url = URL.replace(str(CLIENT_ID), "not-a-uuid")
    elif coordinate == "application_id":
        url = URL.replace(str(APPLICATION_ID), "not-a-uuid")
    else:
        body["application_version_id"] = "not-a-uuid"
    assert client.post(url, headers=HEADERS, json=body).status_code == 422
    assert repository.calls == []


@pytest.mark.parametrize(
    "field", ["cif_version_id", "witnessed_by_user_id", "confirmed_at", "approval_status"]
)
def test_authoritative_extra_field_is_rejected_before_repository(field: str) -> None:
    client, repository = _client()
    body = {**_body(), field: "caller-controlled"}
    assert client.post(URL, headers=HEADERS, json=body).status_code == 422
    assert repository.calls == []


@pytest.mark.parametrize("method", ["GET", "PATCH", "DELETE"])
def test_review_confirmations_collection_exposes_only_post(method: str) -> None:
    client, repository = _client()
    assert client.request(method, URL, headers=HEADERS).status_code == 405
    assert repository.calls == []


@pytest.mark.parametrize("surface", ["public", "client"])
def test_no_public_or_client_confirmation_alias(surface: str) -> None:
    client, repository = _client()
    alias = URL.replace("/api/v1/management/", f"/api/v1/{surface}/")
    assert client.post(alias, headers=HEADERS, json=_body()).status_code == 404
    assert repository.calls == []
