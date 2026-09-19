from __future__ import annotations

import importlib
from types import SimpleNamespace
from urllib.parse import quote
from uuid import UUID

import pytest


AUTH_ID = UUID("11111111-1111-4111-8111-111111111111")
ACTOR_ID = UUID("22222222-2222-4222-8222-222222222222")
CLIENT_ID = UUID("33333333-3333-4333-8333-333333333333")
PERMISSION = "client_onboarding.requirement.review"
REFERENCE = "APP-2026-000124"
BASE_URL = "/api/v1/management/onboarding/applicants/by-reference"
HEADERS = {
    "Authorization": "Bearer synthetic-selection-token",
    "X-Device-Id": "office-selection",
}


def _url(reference: str = REFERENCE) -> str:
    return f"{BASE_URL}/{quote(reference, safe='')}/cif-client"


class SelectionRepository:
    """Only the read boundary is available; any accidental write fails the test."""

    def __init__(
        self,
        *,
        missing=False,
        record_status="eligible_for_cif",
        client_id=CLIENT_ID,
        stored_reference=REFERENCE,
    ):
        self.calls: list[str] = []
        self.record = (
            None
            if missing
            else SimpleNamespace(
                application_reference=stored_reference,
                status=record_status,
                promoted_client_id=client_id,
                full_name="PRIVATE-APPLICANT-NAME",
                phone_number="PRIVATE-PHONE",
                email="PRIVATE-EMAIL",
                present_address="PRIVATE-ADDRESS",
                national_id_egov_evidence_reference="PRIVATE-ID-EVIDENCE",
                baseline_face_scan_evidence_reference="PRIVATE-FACE-EVIDENCE",
            )
        )

    def find_cif_client_by_reference(self, *, application_reference: str):
        self.calls.append(application_reference)
        return self.record


def _client(
    *,
    role="employee",
    permissions=(PERMISSION,),
    account_error=None,
    auth_error=None,
    **kwargs,
):
    # External authentication and PostgreSQL boundaries are replaced; the real
    # router and authenticated_device_context enforce this request's policy.
    from fastapi.testclient import TestClient
    from gilbic_backend.account_repository import AccountContext
    from gilbic_backend.auth_api import (
        account_repository_dependency,
        auth_client_dependency,
    )
    from gilbic_backend.auth_client import AuthSession, SupabaseAuthError
    from gilbic_backend.main import create_app

    class Auth:
        def get_user(self, *, access_token):
            assert access_token == "synthetic-selection-token"
            if auth_error:
                raise SupabaseAuthError("PRIVATE-PROVIDER-DETAIL", status_code=auth_error)
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
            assert device_identifier == "office-selection"
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

    module = importlib.import_module("gilbic_backend.client_onboarding_api")
    repository = SelectionRepository(**kwargs)
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: Auth()
    app.dependency_overrides[account_repository_dependency] = lambda: Accounts()
    app.dependency_overrides[module.client_onboarding_repository_dependency] = (
        lambda: repository
    )
    return TestClient(app), repository


def _assert_private_error(response, expected_status: int) -> None:
    assert response.status_code == expected_status
    assert response.headers.get("cache-control") == "no-store"
    assert set(response.json()) == {"detail"}
    assert "PRIVATE-" not in response.text
    assert str(CLIENT_ID) not in response.text
    assert REFERENCE not in response.text


@pytest.mark.parametrize("role", ["employee", "management"])
def test_authorized_office_lookup_returns_only_canonical_reference_and_stable_client(
    role,
):
    client, repository = _client(role=role)

    response = client.get(_url("app-2026-000124"), headers=HEADERS)

    assert response.status_code == 200
    assert response.json() == {
        "application_reference": "APP-2026-000124",
        "client_id": str(CLIENT_ID),
    }
    assert response.headers.get("cache-control") == "no-store"
    assert repository.calls == ["app-2026-000124"]


@pytest.mark.parametrize(
    "reference,expected",
    [
        (" \tOffice  MiXeD reference\t ", "Office  MiXeD reference"),
        ("Other-" + "long" * 150, "Other-" + "long" * 150),
        ("Office%_literal", "Office%_literal"),
        ("Ref' OR 1=1 --", "Ref' OR 1=1 --"),
        ("Office/2026/  MiXeD", "Office/2026/  MiXeD"),
    ],
)
def test_lookup_delegates_exact_reference_trimming_only_outer_whitespace(
    reference, expected,
):
    client, repository = _client(stored_reference=expected)

    response = client.get(_url(reference), headers=HEADERS)

    assert response.status_code == 200
    assert response.json() == {
        "application_reference": expected,
        "client_id": str(CLIENT_ID),
    }
    assert repository.calls == [expected]


@pytest.mark.parametrize("role", ["collector", "client", "unknown"])
def test_non_office_role_is_denied_even_with_review_permission(role):
    client, repository = _client(role=role)
    response = client.get(_url(), headers=HEADERS)
    _assert_private_error(response, 403)
    assert repository.calls == []


@pytest.mark.parametrize("permissions", [(), ("client_onboarding.bypass",)])
def test_lookup_requires_exact_review_permission(permissions):
    client, repository = _client(permissions=permissions)
    response = client.get(_url(), headers=HEADERS)
    _assert_private_error(response, 403)
    assert repository.calls == []


@pytest.mark.parametrize("omitted,expected", [("Authorization", 401), ("X-Device-Id", 400)])
def test_lookup_requires_authentication_and_device(omitted, expected):
    client, repository = _client()
    headers = {key: value for key, value in HEADERS.items() if key != omitted}
    response = client.get(_url(), headers=headers)
    _assert_private_error(response, expected)
    assert repository.calls == []


@pytest.mark.parametrize("authorization", ["", "Basic synthetic-selection-token", "Bearer "])
def test_invalid_authentication_cannot_read_lookup(authorization):
    client, repository = _client()
    response = client.get(_url(), headers={**HEADERS, "Authorization": authorization})
    _assert_private_error(response, 401)
    assert repository.calls == []


@pytest.mark.parametrize("auth_error", [401, 503])
def test_authentication_provider_errors_do_not_disclose_details(auth_error):
    client, repository = _client(auth_error=auth_error)
    response = client.get(_url(), headers=HEADERS)
    _assert_private_error(response, auth_error)
    assert repository.calls == []


@pytest.mark.parametrize(
    "account_error,expected",
    [
        ("DeviceNotRegistered", 403),
        ("DeviceApprovalRequired", 403),
        ("DeviceRevoked", 403),
        ("AccountDisabled", 403),
        ("AccountNotFound", 401),
    ],
)
def test_lookup_preserves_active_persisted_account_and_device_requirement(
    account_error, expected,
):
    client, repository = _client(account_error=account_error)
    response = client.get(_url(), headers=HEADERS)
    _assert_private_error(response, expected)
    assert repository.calls == []


@pytest.mark.parametrize(
    "repository_options",
    [
        {"missing": True},
        {"record_status": "requirements_incomplete"},
        {"record_status": "under_verification"},
        {"record_status": "requirements_rejected"},
        {"client_id": None},
    ],
)
def test_unavailable_selection_returns_same_generic_not_found(repository_options):
    client, repository = _client(**repository_options)
    response = client.get(_url(), headers=HEADERS)
    _assert_private_error(response, 404)
    assert response.json() == {"detail": "No eligible CIF client is available."}
    assert repository.calls == [REFERENCE]


@pytest.mark.parametrize("reference", ["", "   ", "\t"])
def test_blank_reference_is_rejected_before_repository_lookup(reference):
    client, repository = _client()
    response = client.get(_url(reference), headers=HEADERS)
    _assert_private_error(response, 400)
    assert repository.calls == []


@pytest.mark.parametrize("method", ["POST", "PATCH", "PUT", "DELETE"])
def test_lookup_is_read_only_and_exposes_no_mutation_method(method):
    client, repository = _client()
    response = client.request(method, _url(), headers=HEADERS, json={})
    assert response.status_code == 405
    assert repository.calls == []


@pytest.mark.parametrize("surface", ["public", "client"])
def test_lookup_has_no_public_or_client_self_service_alias(surface):
    client, repository = _client()
    response = client.get(
        _url().replace("/management/", f"/{surface}/"), headers=HEADERS,
    )
    assert response.status_code == 404
    assert repository.calls == []
