from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from gilbic_backend.account_repository import AccountContext
from gilbic_backend.accounting_book_api import (
    accounting_book_repository_dependency,
    create_accounting_book_router,
)
from gilbic_backend.accounting_book_repository import (
    AccountingBookConflict,
    AccountingBookDenied,
    AccountingBookIdentity,
    AccountingBookUnavailable,
)
from gilbic_backend.auth_api import (
    account_repository_dependency,
    auth_client_dependency,
)
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.main import create_app

ACTOR = UUID("11111111-1111-4111-8111-111111111111")
AUTH_ID = UUID("22222222-2222-4222-8222-222222222222")
BOOK_ID = UUID("33333333-3333-4333-8333-333333333333")
HEADERS = {"Authorization": "Bearer synthetic-token", "X-Device-Id": "synthetic-device"}
PATH = "/api/v1/management/financial-accounting/book"
BODY = {
    "kind": "owner_operations",
    "entity_label": "Test owner operations",
    "evidence_reference": "test-evidence:identity",
    "evidence_digest": "a" * 64,
    "confirm": True,
}


class FakeAuth:
    def get_user(self, *, access_token):
        assert access_token == "synthetic-token"
        return AuthSession(
            auth_user_id=AUTH_ID,
            email="test@example.invalid",
            access_token=access_token,
            refresh_token=None,
            expires_at=None,
            email_confirmed=True,
        )


class FakeAccounts:
    def __init__(
        self,
        role="management",
        permissions=("accounting.view", "accounting.journal.manage"),
        status="active",
    ):
        self.role, self.permissions, self.status = role, permissions, status

    def get_context_for_device(self, *, auth_user_id, device_identifier):
        assert auth_user_id == AUTH_ID and device_identifier == "synthetic-device"
        return AccountContext(
            user_id=ACTOR,
            auth_user_id=AUTH_ID,
            username="test",
            email="test@example.invalid",
            full_name="Test User",
            status=self.status,
            roles=(self.role,),
            permissions=self.permissions,
            device_registered=True,
        )


class MemoryBooks:
    """The API tests replace only database I/O, not authorization or validation."""

    def __init__(self):
        self.identity = None
        self.error = None
        self.reads = 0
        self.writes = []

    def get_book_identity(self):
        self.reads += 1
        if self.error:
            raise self.error
        return self.identity

    def configure_book_identity(self, **values):
        self.writes.append(values)
        if self.error:
            raise self.error
        self.identity = AccountingBookIdentity(
            book_id=BOOK_ID,
            configured_at=datetime(2050, 1, 1, tzinfo=timezone.utc),
            configured_by_user_id=values.pop("actor_user_id"),
            **values,
        )
        return self.identity


def client_for(accounts=None, books=None):
    app = FastAPI()
    app.include_router(create_accounting_book_router())
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuth()
    app.dependency_overrides[account_repository_dependency] = lambda: (
        accounts or FakeAccounts()
    )
    app.dependency_overrides[accounting_book_repository_dependency] = lambda: books
    return TestClient(app)


def test_book_identity_endpoint_requires_authentication():
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuth()
    with TestClient(app) as client:
        response = client.get("/api/v1/management/financial-accounting/book")
    assert response.status_code == 401


def test_unconfigured_book_is_visible_without_inventing_identity():
    with client_for(books=MemoryBooks()) as client:
        response = client.get(PATH, headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["data"] == {
        "book": {
            "status": "unconfigured",
            "book_id": None,
            "kind": None,
            "entity_label": None,
            "evidence_reference": None,
            "evidence_digest": None,
            "configured_by_user_id": None,
            "configured_at": None,
        },
        "can_configure": True,
    }


def test_setup_uses_authenticated_actor_and_returns_retained_evidence():
    books = MemoryBooks()
    with client_for(books=books) as client:
        response = client.post(PATH, headers=HEADERS, json=BODY)
    assert response.status_code == 200
    payload = response.json()["data"]["book"]
    assert payload == {
        "status": "configured",
        "book_id": str(BOOK_ID),
        "kind": "owner_operations",
        "entity_label": "Test owner operations",
        "evidence_reference": "test-evidence:identity",
        "evidence_digest": "a" * 64,
        "configured_by_user_id": str(ACTOR),
        "configured_at": "2050-01-01T00:00:00+00:00",
    }


@pytest.mark.parametrize(
    "role,permissions,status",
    [
        ("client", ("accounting.view", "accounting.journal.manage"), "active"),
        ("management", (), "active"),
        ("management", ("accounting.view", "accounting.journal.manage"), "inactive"),
    ],
)
def test_denied_actor_never_reads_identity_or_evidence(role, permissions, status):
    books = MemoryBooks()
    with client_for(FakeAccounts(role, permissions, status), books) as client:
        response = client.get(PATH, headers=HEADERS)
        write = client.post(PATH, headers=HEADERS, json=BODY)
    assert response.status_code == write.status_code == 403
    assert books.reads == 0 and books.writes == []


def test_view_only_manager_cannot_configure():
    books = MemoryBooks()
    with client_for(FakeAccounts(permissions=("accounting.view",)), books) as client:
        assert (
            client.get(PATH, headers=HEADERS).json()["data"]["can_configure"] is False
        )
        assert client.post(PATH, headers=HEADERS, json=BODY).status_code == 403
    assert books.writes == []


@pytest.mark.parametrize(
    "change,expected",
    [
        ({"confirm": False}, 409),
        ({"confirm": "true"}, 422),
        ({"kind": "company"}, 422),
        ({"evidence_digest": "invalid"}, 422),
        ({"entity_label": " "}, 422),
        ({"evidence_reference": " ref "}, 422),
        ({"database_url": "postgresql://untrusted"}, 422),
        ({"actor_user_id": str(BOOK_ID)}, 422),
    ],
)
def test_invalid_or_unconfirmed_setup_has_no_write(change, expected):
    books = MemoryBooks()
    with client_for(books=books) as client:
        response = client.post(PATH, headers=HEADERS, json=BODY | change)
    assert response.status_code == expected
    assert books.writes == []


@pytest.mark.parametrize(
    "error,expected",
    [
        (AccountingBookConflict("Changed identity"), 409),
        (AccountingBookDenied("Denied"), 403),
        (AccountingBookUnavailable("Unavailable"), 503),
    ],
)
def test_database_errors_are_explicit_without_fake_success(error, expected):
    books = MemoryBooks()
    books.error = error
    with client_for(books=books) as client:
        response = client.post(PATH, headers=HEADERS, json=BODY)
    assert response.status_code == expected
    assert response.json()["detail"]["code"] == error.code


def test_mobile_alias_has_identical_authentication_and_response():
    with client_for(books=MemoryBooks()) as client:
        mobile = PATH.replace("/api/v1/", "/api/mobile/v1/")
        assert client.get(mobile).status_code == 401
        assert (
            client.get(mobile, headers=HEADERS).json()
            == client.get(PATH, headers=HEADERS).json()
        )
