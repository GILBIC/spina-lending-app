from datetime import date
from uuid import UUID

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from gilbic_backend.account_repository import AccountContext, DeviceApprovalRequired
from gilbic_backend.accounting_export import AccountingExportError
from gilbic_backend.accounting_export_api import (
    accounting_export_repository_dependency,
    create_accounting_export_router,
)
from gilbic_backend.auth_api import (
    account_repository_dependency,
    auth_client_dependency,
)
from gilbic_backend.auth_client import AuthSession
from test_accounting_export import ACTOR, sample_snapshot

PATH = "/api/v1/management/financial-accounting/export"
QUERY = "?start_date=2026-09-01&end_date=2026-09-30"
HEADERS = {"Authorization": "Bearer synthetic", "X-Device-Id": "synthetic-device"}


class Auth:
    def get_user(self, *, access_token):
        return AuthSession(
            auth_user_id=ACTOR,
            email="synthetic@example.invalid",
            access_token=access_token,
            refresh_token=None,
            expires_at=None,
            email_confirmed=True,
        )


class Accounts:
    def __init__(self, role="management", permission=True, approved=True):
        self.role, self.permission, self.approved = role, permission, approved

    def get_context_for_device(self, *, auth_user_id: UUID, device_identifier):
        if not self.approved:
            raise DeviceApprovalRequired("Device approval required")
        return AccountContext(
            user_id=ACTOR,
            auth_user_id=auth_user_id,
            username="synthetic",
            email="synthetic@example.invalid",
            full_name="Synthetic Manager",
            status="active",
            roles=(self.role,),
            permissions=("accounting.view",) if self.permission else (),
            device_registered=True,
        )


class Repository:
    def __init__(self, error=None):
        self.called = False
        self.error = error

    def load_snapshot(self, *, start_date, end_date):
        self.called = True
        assert start_date == date(2026, 9, 1) and end_date == date(2026, 9, 30)
        if self.error:
            raise self.error
        return sample_snapshot()


def client(*, role="management", permission=True, approved=True, error=None):
    app = FastAPI()
    app.include_router(create_accounting_export_router())
    repository = Repository(error)
    app.dependency_overrides[auth_client_dependency] = lambda: Auth()
    app.dependency_overrides[account_repository_dependency] = lambda: Accounts(
        role, permission, approved
    )
    app.dependency_overrides[accounting_export_repository_dependency] = lambda: (
        repository
    )
    return TestClient(app), repository


def test_protected_zip_response_has_safe_headers():
    http, repository = client()
    response = http.get(PATH + QUERY, headers=HEADERS)
    assert response.status_code == 200
    assert repository.called
    assert response.headers["content-type"] == "application/zip"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert (
        response.headers["content-disposition"]
        == 'attachment; filename="spina-accounting-2026-09-01-to-2026-09-30.zip"'
    )
    assert response.content.startswith(b"PK")


@pytest.mark.parametrize(
    "options,headers,status",
    [
        ({}, {}, 401),
        ({}, {"Authorization": "Bearer synthetic"}, 400),
        ({"role": "collector"}, HEADERS, 403),
        ({"permission": False}, HEADERS, 403),
        ({"approved": False}, HEADERS, 403),
    ],
)
def test_authorization_fails_before_read(options, headers, status):
    http, repository = client(**options)
    assert http.get(PATH + QUERY, headers=headers).status_code == status
    assert not repository.called


@pytest.mark.parametrize(
    "query",
    [
        "",
        "?start_date=bad&end_date=2026-09-30",
        "?start_date=1788220800&end_date=2026-09-30",
        "?start_date=2026-09-01T00:00:00Z&end_date=2026-09-30",
        "?start_date=2026-09-30&end_date=2026-09-01",
        "?start_date=2025-01-01&end_date=2026-09-30",
    ],
)
def test_invalid_dates_fail_before_read(query):
    http, repository = client()
    assert http.get(PATH + query, headers=HEADERS).status_code == 422
    assert not repository.called


@pytest.mark.parametrize(
    "error,status",
    [
        (AccountingExportError("oversized", "Too large"), 413),
        (AccountingExportError("integrity", "Not balanced"), 409),
        (psycopg.OperationalError("private database secret"), 503),
    ],
)
def test_safe_errors_never_return_partial_download(error, status):
    http, _ = client(error=error)
    response = http.get(PATH + QUERY, headers=HEADERS)
    assert response.status_code == status
    assert "private database secret" not in response.text
    assert "content-disposition" not in response.headers


def test_no_posting_route():
    http, repository = client()
    assert http.post(PATH + QUERY, headers=HEADERS).status_code == 405
    assert not repository.called
