"""Credential continuation reuses authenticated device policy and exact permission."""

from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gilbic_backend import first_loan_credential_api as module
from gilbic_backend.account_repository import AccountConflict, DeviceRevoked
from gilbic_backend.first_loan_credential_service import FirstLoanCredentialAccessDenied

ACTOR = UUID("11111111-1111-4111-8111-111111111111")
AUTH = UUID("22222222-2222-4222-8222-222222222222")
DEVICE = UUID("33333333-3333-4333-8333-333333333333")
LOAN = UUID("44444444-4444-4444-8444-444444444444")
PERMISSION = "client.credential.manage"
HEADERS = {
    "Authorization": "Bearer synthetic-credential-token",
    "X-Device-Id": "synthetic-credential-device",
}
URL = f"/api/v1/management/first-loans/{LOAN}/credentials"


def client(
    role="employee",
    permissions=(PERMISSION,),
    registered=True,
    revoked=False,
    error=None,
):
    calls = []

    class Auth:
        def get_user(self, *, access_token):
            assert access_token == "synthetic-credential-token"
            return SimpleNamespace(auth_user_id=AUTH)

    class Accounts:
        def get_context_for_device(self, *, auth_user_id, device_identifier):
            assert (
                auth_user_id == AUTH
                and device_identifier == "synthetic-credential-device"
            )
            if revoked:
                raise DeviceRevoked("Synthetic revoked device")
            return SimpleNamespace(
                user_id=ACTOR,
                roles=(role,),
                permissions=permissions,
                registered_device_id=DEVICE if registered else None,
            )

    class Service:
        def provision(self, **arguments):
            calls.append(arguments)
            if error:
                raise error
            return {
                "status": "completed",
                "username": "synthetic",
                "credentials": {"password": "one-time-synthetic"},
            }

    app = FastAPI()
    app.include_router(module.create_first_loan_credential_router())
    app.dependency_overrides[module.auth_client_dependency] = Auth
    app.dependency_overrides[module.account_repository_dependency] = Accounts
    app.dependency_overrides[module.first_loan_credential_service_dependency] = Service
    return TestClient(app), calls


@pytest.mark.parametrize("role", ["employee", "management"])
def test_authorized_office_actor_and_registered_device_are_forwarded_once_with_no_store(
    role,
):
    http, calls = client(role=role)
    response = http.post(URL, headers=HEADERS)
    assert (
        response.status_code == 200 and response.headers["cache-control"] == "no-store"
    )
    assert calls == [
        {"loan_id": LOAN, "actor_user_id": ACTOR, "registered_device_id": DEVICE}
    ]
    assert response.json()["credentials"]["password"] == "one-time-synthetic"


@pytest.mark.parametrize(
    "role,permissions",
    [
        ("client", (PERMISSION,)),
        ("collector", (PERMISSION,)),
        ("employee", ("account.manage",)),
        ("management", (PERMISSION + ".extra",)),
    ],
)
def test_role_and_exact_credential_permission_reject_before_external_account_work(
    role, permissions
):
    http, calls = client(role=role, permissions=permissions)
    response = http.post(URL, headers=HEADERS)
    assert (
        response.status_code == 403 and response.headers["cache-control"] == "no-store"
    )
    assert calls == []


@pytest.mark.parametrize(
    "headers,status", [({}, 401), ({"Authorization": HEADERS["Authorization"]}, 400)]
)
def test_credentials_require_authentication_and_device_header(headers, status):
    http, calls = client()
    response = http.post(URL, headers=headers)
    assert (
        response.status_code == status
        and response.headers["cache-control"] == "no-store"
        and calls == []
    )


@pytest.mark.parametrize("options", [{"registered": False}, {"revoked": True}])
def test_credentials_require_a_persisted_active_device(options):
    http, calls = client(**options)
    response = http.post(URL, headers=HEADERS)
    assert (
        response.status_code == 403
        and response.headers["cache-control"] == "no-store"
        and calls == []
    )


@pytest.mark.parametrize(
    "error,status",
    [
        (AccountConflict("No committed release."), 409),
        (FirstLoanCredentialAccessDenied("Actor revoked."), 403),
    ],
)
def test_persisted_release_or_actor_rejection_has_private_error_response(error, status):
    http, calls = client(error=error)
    response = http.post(URL, headers=HEADERS)
    assert (
        response.status_code == status
        and response.headers["cache-control"] == "no-store"
    )
    assert len(calls) == 1 and "credentials" not in response.json()


def test_invalid_loan_identity_is_no_store_and_never_reaches_service():
    http, calls = client()
    response = http.post(
        "/api/v1/management/first-loans/not-a-uuid/credentials", headers=HEADERS
    )
    assert (
        response.status_code == 422
        and response.headers["cache-control"] == "no-store"
        and calls == []
    )
