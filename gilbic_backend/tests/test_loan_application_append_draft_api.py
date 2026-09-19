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
VERSION_7_ID = UUID("55555555-5555-4555-8555-555555555557")
VERSION_8_ID = UUID("55555555-5555-4555-8555-555555555558")
CIF_ID = UUID("66666666-6666-4666-8666-666666666666")
PERMISSION = "client_onboarding.requirement.review"
EXPECTED_VERSION = 7
URL = (
    f"/api/v1/management/clients/{CLIENT_ID}/loan-applications/"
    f"{APPLICATION_ID}/draft-versions"
)
ROUTE_PATH = (
    "/api/v1/management/clients/{client_id}/loan-applications/"
    "{application_id}/draft-versions"
)
HEADERS = {
    "Authorization": "Bearer synthetic-application-append-token",
    "X-Device-Id": "office-application-append",
}
RECORDED_AT = datetime(2026, 9, 18, 3, 4, 5, tzinfo=timezone.utc)


def _information(*, complete: bool) -> LoanApplicationInformation:
    if not complete:
        return LoanApplicationInformation()
    return LoanApplicationInformation(
        request={
            "requested_loan_type_id": "00000000-0000-0000-0000-0000000000a1",
            "purpose": "Synthetic corrected working capital",
            "requested_amount": "5000.00",
            "requested_payment_arrangement": "Daily office collection",
            "requested_term": "75 calendar days",
        },
        repayment={
            "repayment_source": "Synthetic microbusiness",
            "source_details": "Synthetic updated income declaration",
            "monthly_gross_income": "15000.00",
            "monthly_net_income": "9000.00",
            "has_existing_obligations": False,
        },
    )


def _body(*, complete: bool = True) -> dict[str, object]:
    return {
        "cif_version_id": str(CIF_ID),
        "expected_version_number": EXPECTED_VERSION,
        "information": (
            _information(complete=True).model_dump(mode="json") if complete else {}
        ),
    }


class AppendRepository:
    def __init__(self, *, saved_version: int = 8, error: str | None = None):
        self.calls: list[dict[str, object]] = []
        self.saved_version = saved_version
        self.error = error

    def append_draft(self, **payload):
        self.calls.append(payload)
        module = importlib.import_module("gilbic_backend.loan_application_repository")
        conflicts = {
            "stale": "Application version changed; refresh before saving.",
            "different": "Application version has already advanced with different data.",
            "source": "No eligible current CIF is available for this application draft.",
        }
        if self.error in conflicts:
            raise module.LoanApplicationConflict(conflicts[self.error])
        if self.error == "access":
            raise module.LoanApplicationAccessDenied(
                "An active authorized office account is required."
            )
        return SimpleNamespace(
            id=VERSION_8_ID if self.saved_version == 8 else VERSION_7_ID,
            application_id=payload["application_id"],
            application_reference="SYN-APP-DRAFT-001",
            client_id=payload["client_id"],
            cif_version_id=payload["cif_version_id"],
            version_number=self.saved_version,
            information=payload["information"],
            recorded_by_user_id=ACTOR_ID,
            recorded_at=RECORDED_AT,
            private_evidence_reference="PRIVATE-EVIDENCE",
            approval_status="approved",
            release_status="released",
        )


def _client(
    *,
    role: str = "employee",
    permissions: tuple[str, ...] = (PERMISSION,),
    saved_version: int = 8,
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
            assert access_token == "synthetic-application-append-token"
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
            assert device_identifier == "office-application-append"
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

    repository = AppendRepository(saved_version=saved_version, error=repository_error)
    app = create_app()
    if "post" not in app.openapi().get("paths", {}).get(ROUTE_PATH, {}):
        pytest.fail("Loan application draft version API is not implemented")
    app.dependency_overrides[auth_client_dependency] = lambda: Auth()
    app.dependency_overrides[account_repository_dependency] = lambda: Accounts()
    app.dependency_overrides[
        module.loan_application_repository_dependency
    ] = lambda: repository
    return TestClient(app), repository


@pytest.mark.parametrize("role", ["employee", "management"])
@pytest.mark.parametrize("complete", [True, False])
def test_office_actor_appends_exact_saved_application_version(
    role: str, complete: bool
) -> None:
    client, repository = _client(role=role)
    information = _information(complete=complete)

    response = client.post(URL, headers=HEADERS, json=_body(complete=complete))

    assert response.status_code == 200
    assert response.json() == {
        "client_id": str(CLIENT_ID),
        "application_id": str(APPLICATION_ID),
        "application_version_id": str(VERSION_8_ID),
        "application_reference": "SYN-APP-DRAFT-001",
        "cif_version_id": str(CIF_ID),
        "version_number": 8,
        "information": information.model_dump(mode="json"),
        "missing_fields": list(information.missing_fields()),
        "recorded_at": "2026-09-18T03:04:05Z",
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
            "cif_version_id": CIF_ID,
            "expected_version_number": EXPECTED_VERSION,
            "information": information,
        }
    ]


def test_unchanged_save_returns_repository_version_without_http_increment() -> None:
    client, repository = _client(saved_version=7)

    response = client.post(URL, headers=HEADERS, json=_body())

    assert response.status_code == 200
    assert response.json()["application_version_id"] == str(VERSION_7_ID)
    assert response.json()["version_number"] == 7
    assert len(repository.calls) == 1


def test_exact_retry_delegates_each_time_and_preserves_saved_identity() -> None:
    client, repository = _client()
    body = _body()

    first = client.post(URL, headers=HEADERS, json=body)
    repeated = client.post(URL, headers=HEADERS, json=body)

    assert first.status_code == repeated.status_code == 200
    assert first.json() == repeated.json()
    assert first.json()["application_version_id"] == str(VERSION_8_ID)
    assert first.json()["recorded_at"] == "2026-09-18T03:04:05Z"
    assert len(repository.calls) == 2
    assert repository.calls[0] == repository.calls[1]


@pytest.mark.parametrize("role", ["collector", "client"])
def test_non_office_role_cannot_append_even_with_permission(role: str) -> None:
    client, repository = _client(role=role)
    assert client.post(URL, headers=HEADERS, json=_body()).status_code == 403
    assert repository.calls == []


def test_append_requires_permission() -> None:
    client, repository = _client(permissions=())
    assert client.post(URL, headers=HEADERS, json=_body()).status_code == 403
    assert repository.calls == []


@pytest.mark.parametrize("omitted,expected", [("Authorization", 401), ("X-Device-Id", 400)])
def test_append_requires_authentication_and_device(omitted: str, expected: int) -> None:
    client, repository = _client()
    headers = {key: value for key, value in HEADERS.items() if key != omitted}
    assert client.post(URL, headers=headers, json=_body()).status_code == expected
    assert repository.calls == []


@pytest.mark.parametrize(
    "error", ["DeviceNotRegistered", "DeviceRevoked", "AccountDisabled"]
)
def test_append_preserves_account_and_device_denials(error: str) -> None:
    client, repository = _client(account_error=error)
    response = client.post(URL, headers=HEADERS, json=_body())
    assert response.status_code == 403
    assert response.json() == {"detail": "Synthetic access denial."}
    assert repository.calls == []


@pytest.mark.parametrize(
    "error,expected_status,expected_detail",
    [
        ("access", 403, "An active authorized office account is required."),
        ("stale", 409, "Application version changed; refresh before saving."),
        (
            "different",
            409,
            "Application version has already advanced with different data.",
        ),
        (
            "source",
            409,
            "No eligible current CIF is available for this application draft.",
        ),
    ],
)
def test_append_maps_repository_denials(
    error: str, expected_status: int, expected_detail: str
) -> None:
    client, repository = _client(repository_error=error)
    response = client.post(URL, headers=HEADERS, json=_body())
    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}
    assert len(repository.calls) == 1


@pytest.mark.parametrize(
    "field", ["cif_version_id", "expected_version_number", "information"]
)
def test_required_append_field_is_rejected_before_repository(field: str) -> None:
    client, repository = _client()
    body = _body()
    del body[field]
    assert client.post(URL, headers=HEADERS, json=body).status_code == 422
    assert repository.calls == []


@pytest.mark.parametrize("value", [True, 7.0, "7", 0, -1])
def test_expected_version_must_be_strict_positive_integer(value: object) -> None:
    client, repository = _client()
    body = {**_body(), "expected_version_number": value}
    assert client.post(URL, headers=HEADERS, json=body).status_code == 422
    assert repository.calls == []


def test_invalid_nested_information_is_rejected_before_repository() -> None:
    client, repository = _client()
    body = {
        **_body(),
        "information": {
            "request": {"requested_amount": "1.001"},
            "repayment": {},
        },
    }
    assert client.post(URL, headers=HEADERS, json=body).status_code == 422
    assert repository.calls == []


@pytest.mark.parametrize("field", ["recorded_by_user_id", "approval_status"])
def test_authoritative_extra_field_is_rejected_before_repository(field: str) -> None:
    client, repository = _client()
    body = {**_body(), field: "caller-controlled"}
    assert client.post(URL, headers=HEADERS, json=body).status_code == 422
    assert repository.calls == []


@pytest.mark.parametrize(
    "coordinate", ["client_id", "application_id", "cif_version_id"]
)
def test_malformed_identity_is_rejected_before_repository(coordinate: str) -> None:
    client, repository = _client()
    url = URL
    body = _body()
    if coordinate == "client_id":
        url = URL.replace(str(CLIENT_ID), "not-a-uuid")
    elif coordinate == "application_id":
        url = URL.replace(str(APPLICATION_ID), "not-a-uuid")
    else:
        body["cif_version_id"] = "not-a-uuid"
    assert client.post(url, headers=HEADERS, json=body).status_code == 422
    assert repository.calls == []


@pytest.mark.parametrize("method", ["GET", "DELETE"])
def test_draft_versions_collection_exposes_only_post(method: str) -> None:
    client, repository = _client()
    assert client.request(method, URL, headers=HEADERS).status_code == 405
    assert repository.calls == []


@pytest.mark.parametrize("surface", ["public", "client"])
def test_no_public_or_client_append_alias(surface: str) -> None:
    client, repository = _client()
    alias = URL.replace("/api/v1/management/", f"/api/v1/{surface}/")
    assert client.post(alias, headers=HEADERS, json=_body()).status_code == 404
    assert repository.calls == []
