from __future__ import annotations

import importlib
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest

from gilbic_backend.loan_application_information import LoanApplicationInformation


AUTH_ID = UUID("11111111-1111-4111-8111-111111111111")
ACTOR_ID = UUID("22222222-2222-4222-8222-222222222222")
CLIENT_ID = UUID("33333333-3333-4333-8333-333333333333")
APPLICATION_ID = UUID("44444444-4444-4444-8444-444444444444")
VERSION_ID = UUID("55555555-5555-4555-8555-555555555555")
CIF_ID = UUID("66666666-6666-4666-8666-666666666666")
VERSION_NUMBER = 7
PERMISSION = "client_onboarding.requirement.review"
URL = (
    f"/api/v1/management/clients/{CLIENT_ID}/loan-applications/"
    f"{APPLICATION_ID}/versions/{VERSION_NUMBER}/review-summary"
)
HEADERS = {
    "Authorization": "Bearer synthetic-application-review-token",
    "X-Device-Id": "office-application-review",
}
RECORDED_AT = datetime(2026, 9, 17, 1, 2, 3, tzinfo=timezone.utc)


def _information(*, complete: bool) -> LoanApplicationInformation:
    return LoanApplicationInformation(
        request={
            "requested_loan_type_id": "00000000-0000-0000-0000-0000000000a1",
            "purpose": "Synthetic working capital" if complete else None,
            "requested_amount": "3000.00",
            "requested_payment_arrangement": "Daily office collection",
            "requested_term": "60 calendar days",
        },
        repayment={
            "repayment_source": "Synthetic microbusiness",
            "source_details": "Synthetic sari-sari income declaration",
            "monthly_gross_income": "12000.00",
            "monthly_net_income": "8000.00",
            "has_existing_obligations": False,
        },
    )


class SummaryRepository:
    def __init__(self, *, complete: bool = True, error: str | None = None):
        self.calls: list[dict[str, object]] = []
        self.complete = complete
        self.error = error

    def get_version(self, **payload):
        self.calls.append(payload)
        module = importlib.import_module("gilbic_backend.loan_application_repository")
        if self.error == "conflict":
            raise module.LoanApplicationConflict("Application version was not found.")
        if self.error == "access":
            raise module.LoanApplicationAccessDenied(
                "An active authorized office account is required."
            )
        return SimpleNamespace(
            id=VERSION_ID,
            application_id=APPLICATION_ID,
            application_reference="SYN-APP-REVIEW-001",
            client_id=CLIENT_ID,
            cif_version_id=CIF_ID,
            version_number=payload["version_number"],
            information=_information(complete=self.complete),
            recorded_by_user_id=ACTOR_ID,
            recorded_at=RECORDED_AT,
            private_evidence_reference="PRIVATE-EVIDENCE",
            approval_status="approved",
            release_status="released",
        )


def _application_api():
    try:
        module = importlib.import_module("gilbic_backend.loan_application_api")
    except ModuleNotFoundError as error:
        if error.name == "gilbic_backend.loan_application_api":
            pytest.fail("Loan application review summary API is not implemented")
        raise
    if not hasattr(module, "loan_application_repository_dependency"):
        pytest.fail("Loan application review summary API is not implemented")
    return module


def _client(
    *,
    role: str = "employee",
    permissions: tuple[str, ...] = (PERMISSION,),
    complete: bool = True,
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

    class Auth:
        def get_user(self, *, access_token):
            assert access_token == "synthetic-application-review-token"
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
            assert device_identifier == "office-application-review"
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

    module = _application_api()
    repository = SummaryRepository(complete=complete, error=repository_error)
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: Auth()
    app.dependency_overrides[account_repository_dependency] = lambda: Accounts()
    app.dependency_overrides[
        module.loan_application_repository_dependency
    ] = lambda: repository
    return TestClient(app), repository


@pytest.mark.parametrize("role", ["employee", "management"])
@pytest.mark.parametrize("complete", [True, False])
def test_office_review_returns_exact_saved_application_version(
    role: str, complete: bool
) -> None:
    client, repository = _client(role=role, complete=complete)

    response = client.get(URL, headers=HEADERS)

    information = _information(complete=complete)
    assert response.status_code == 200
    assert response.json() == {
        "client_id": str(CLIENT_ID),
        "application_id": str(APPLICATION_ID),
        "application_version_id": str(VERSION_ID),
        "application_reference": "SYN-APP-REVIEW-001",
        "cif_version_id": str(CIF_ID),
        "version_number": VERSION_NUMBER,
        "information": information.model_dump(mode="json"),
        "missing_fields": list(information.missing_fields()),
        "recorded_at": "2026-09-17T01:02:03Z",
        "review_scope": "loan_application_information_only",
    }
    assert "no-store" in response.headers.get("cache-control", "").lower()
    assert "PRIVATE-EVIDENCE" not in response.text
    assert "approved" not in response.text and "released" not in response.text
    assert repository.calls == [
        {
            "actor_user_id": ACTOR_ID,
            "client_id": CLIENT_ID,
            "application_id": APPLICATION_ID,
            "version_number": VERSION_NUMBER,
        }
    ]


@pytest.mark.parametrize("role", ["collector", "client"])
def test_non_office_role_cannot_read_application_review_with_permission(
    role: str,
) -> None:
    client, repository = _client(role=role)
    assert client.get(URL, headers=HEADERS).status_code == 403
    assert repository.calls == []


def test_application_review_requires_permission() -> None:
    client, repository = _client(permissions=())
    assert client.get(URL, headers=HEADERS).status_code == 403
    assert repository.calls == []


@pytest.mark.parametrize("omitted,expected", [("Authorization", 401), ("X-Device-Id", 400)])
def test_application_review_requires_authentication_and_device(
    omitted: str, expected: int
) -> None:
    client, repository = _client()
    headers = {key: value for key, value in HEADERS.items() if key != omitted}
    assert client.get(URL, headers=headers).status_code == expected
    assert repository.calls == []


@pytest.mark.parametrize(
    "error", ["DeviceNotRegistered", "DeviceRevoked", "AccountDisabled"]
)
def test_application_review_preserves_account_and_device_denials(error: str) -> None:
    client, repository = _client(account_error=error)
    response = client.get(URL, headers=HEADERS)
    assert response.status_code == 403
    assert response.json() == {"detail": "Synthetic access denial."}
    assert repository.calls == []


@pytest.mark.parametrize(
    "error,expected_status,expected_detail",
    [
        ("conflict", 409, "Application version was not found."),
        ("access", 403, "An active authorized office account is required."),
    ],
)
def test_application_review_maps_repository_denials(
    error: str, expected_status: int, expected_detail: str
) -> None:
    client, repository = _client(repository_error=error)
    response = client.get(URL, headers=HEADERS)
    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}
    assert len(repository.calls) == 1


@pytest.mark.parametrize("method", ["POST", "PATCH", "DELETE"])
def test_review_summary_is_not_a_mutation_endpoint(method: str) -> None:
    client, repository = _client()
    assert client.request(method, URL, headers=HEADERS, json={}).status_code == 405
    assert repository.calls == []


@pytest.mark.parametrize("surface", ["public", "client"])
def test_no_public_or_client_application_review_alias(surface: str) -> None:
    client, repository = _client()
    alias = URL.replace("/api/v1/management/", f"/api/v1/{surface}/")
    assert client.get(alias, headers=HEADERS).status_code == 404
    assert repository.calls == []


@pytest.mark.parametrize("version", ["0", "-1", "not-a-number"])
def test_invalid_application_version_is_rejected_before_repository(version: str) -> None:
    client, repository = _client()
    url = URL.replace(
        f"/versions/{VERSION_NUMBER}/", f"/versions/{version}/"
    )
    assert client.get(url, headers=HEADERS).status_code == 422
    assert repository.calls == []


@pytest.mark.parametrize("coordinate", ["client", "application"])
def test_malformed_identity_is_rejected_before_repository(coordinate: str) -> None:
    client, repository = _client()
    old = str(CLIENT_ID if coordinate == "client" else APPLICATION_ID)
    assert client.get(URL.replace(old, "not-a-uuid"), headers=HEADERS).status_code == 422
    assert repository.calls == []
