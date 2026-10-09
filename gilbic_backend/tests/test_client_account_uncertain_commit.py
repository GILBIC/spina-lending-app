"""Exercise the manual route/repository with offline SQL and Auth boundaries."""

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from gilbic_backend.client_account_api import (
    client_account_repository_dependency,
    client_credential_mailer_dependency,
    create_client_account_router,
)
from gilbic_backend.credential_mailer import CredentialDeliveryResult
from gilbic_backend.management_api import (
    management_account_repository_dependency,
    management_auth_admin_dependency,
    management_auth_client_dependency,
)
from psycopg import OperationalError
from test_client_account_creation_compensation import (
    CLIENT_ID,
    DEVICE_ID,
    TARGET_AUTH_ID,
    FakeAccounts,
    FakeAuthClient,
)

from gilbic_backend import client_account_repository, management_repository

USER_ID = UUID("55555555-5555-4555-8555-555555555555")
OTHER_AUTH_ID = UUID("77777777-7777-4777-8777-777777777777")
HEADERS = {"Authorization": "Bearer management-token", "X-Device-Id": DEVICE_ID}
PAYLOAD = {"client_id": str(CLIENT_ID), "email": "client@example.com"}


class SqlBoundary:
    def __init__(self, *, lose_ack=True, fail_readback=False, reject_link=False):
        self.lose_ack = lose_ack
        self.fail_readback = fail_readback
        self.reject_link = reject_link
        self.borrower_user_id = None
        self.borrower_status = "active"
        self.account = None
        self.committed = False
        self.queries = []

    @contextmanager
    def connect(self):
        if self.committed and self.fail_readback:
            raise OperationalError("Synthetic readback unavailable")
        yield self

    @contextmanager
    def transaction(self):
        snapshot = deepcopy(self.account), self.borrower_user_id
        try:
            yield self
        except Exception:
            self.account, self.borrower_user_id = snapshot
            raise
        if self.account is not None and not self.committed:
            self.committed = True
            if self.lose_ack:
                raise OperationalError(
                    "Synthetic COMMIT succeeded, acknowledgement lost"
                )

    def cursor(self, **kwargs):
        return SqlCursor(self)


class SqlCursor:
    def __init__(self, state):
        self.state = state
        self.row = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params=()):
        q = " ".join(query.split()).lower()
        state = self.state
        state.queries.append(q)
        self.row = None
        if "from lending.client_onboarding_applicants" in q:
            pass  # Imported borrower, outside the office first-loan lifecycle.
        elif "from lending.clients" in q and "join core.users" in q:
            account = state.account
            if (
                account
                and params
                == (CLIENT_ID, TARGET_AUTH_ID, "spina.c.001", "client@example.com")
                and state.borrower_user_id == account["id"]
                and account["external_auth_id"] == params[1]
                and account["username"] == params[2]
                and account["email"] == params[3]
            ):
                self.row = (state.borrower_user_id,)
        elif "from lending.clients" in q:
            assert params == (CLIENT_ID,)
            self.row = {
                "id": CLIENT_ID,
                "client_code": "C-001",
                "full_name": "Synthetic Borrower",
                "status": state.borrower_status,
                "user_id": state.borrower_user_id,
            }
        elif "select 1 from core.users where lower(username)" in q:
            self.row = (1,) if state.account else None
        elif "select id from core.roles" in q:
            self.row = (UUID("66666666-6666-4666-8666-666666666666"),)
        elif "insert into core.users" in q:
            now = datetime(2026, 10, 6, tzinfo=UTC)
            state.account = {
                "id": USER_ID,
                "username": params[0],
                "email": params[1],
                "full_name": params[2],
                "external_auth_id": params[3],
                "status": "active",
                "roles": ["client"],
                "device_count": 0,
                "created_at": now,
                "updated_at": now,
            }
            self.row = (USER_ID,)
        elif "update lending.clients" in q:
            assert params[1] == CLIENT_ID
            state.borrower_user_id = params[0]
        elif "from core.users u" in q:
            self.row = state.account
        elif "select id from core.users where id" in q:
            assert params == (USER_ID,)
            self.row = (USER_ID,) if state.account else None
        elif "insert into core.user_roles" in q or "insert into core.audit_logs" in q:
            pass
        else:
            raise AssertionError(f"Unexpected SQL: {q}")
        return self

    def fetchone(self):
        return self.row

    def fetchall(self):
        return [self.row] if self.row else []


class AuthBoundary:
    def __init__(self, sql):
        self.sql = sql
        self.users = {}
        self.creates = 0
        self.deletes = []

    def create_user(self, *, email, password, email_confirm):
        assert email == "client@example.com" and email_confirm
        self.creates += 1
        self.users[TARGET_AUTH_ID] = password
        if self.sql.reject_link:
            self.sql.borrower_status = "suspended"
        return TARGET_AUTH_ID

    def delete_user(self, *, auth_user_id):
        self.deletes.append(auth_user_id)
        self.users.pop(auth_user_id, None)
        # The real FK sets the local Auth link to NULL on Auth deletion.
        if self.sql.account and self.sql.account["external_auth_id"] == auth_user_id:
            self.sql.account["external_auth_id"] = None

    def update_user_password(self, *, auth_user_id, password):
        assert auth_user_id in self.users
        self.users[auth_user_id] = password


class MailBoundary:
    def __init__(self):
        self.deliveries = []

    def send_client_credentials(self, **kwargs):
        self.deliveries.append(kwargs)
        return CredentialDeliveryResult(sent=True, detail="Synthetic delivery")


@pytest.fixture
def account_flow(monkeypatch):
    def make(**kwargs):
        sql = SqlBoundary(**kwargs)
        admin = AuthBoundary(sql)
        mailer = MailBoundary()
        repository = client_account_repository.PostgresClientAccountRepository()
        monkeypatch.setattr(client_account_repository, "open_connection", sql.connect)
        monkeypatch.setattr(management_repository, "open_connection", sql.connect)
        app = FastAPI()
        app.include_router(create_client_account_router())
        app.dependency_overrides[management_auth_client_dependency] = FakeAuthClient
        accounts = FakeAccounts()
        original_context = accounts.get_context_for_device

        def context(**kwargs):
            return replace(
                original_context(**kwargs),
                permissions=("account.manage", "client.credential.manage"),
            )

        accounts.get_context_for_device = context
        app.dependency_overrides[management_account_repository_dependency] = lambda: (
            accounts
        )
        app.dependency_overrides[management_auth_admin_dependency] = lambda: admin
        app.dependency_overrides[client_account_repository_dependency] = lambda: (
            repository
        )
        app.dependency_overrides[client_credential_mailer_dependency] = lambda: mailer
        return TestClient(app, raise_server_exceptions=False), sql, admin, mailer

    return make


def assert_existing_account_recovery(client, sql, admin):
    accounts = client.get("/api/v1/management/client-accounts", headers=HEADERS)
    assert accounts.status_code == 200
    assert accounts.json()["data"]["accounts"][0]["id"] == str(USER_ID)
    retry = client.post(
        "/api/v1/management/client-accounts", headers=HEADERS, json=PAYLOAD
    )
    assert retry.status_code == 409 and "already linked" in retry.text
    reset = client.post(
        f"/api/v1/management/accounts/{USER_ID}/password/reset", headers=HEADERS
    )
    assert reset.status_code == 200, reset.text
    assert (
        admin.users[TARGET_AUTH_ID] == reset.json()["data"]["credentials"]["password"]
    )
    assert sql.account["external_auth_id"] == TARGET_AUTH_ID
    assert admin.creates == 1 and not admin.deletes


def test_commit_ack_loss_reconciles_exact_account_and_keeps_password_reset(
    account_flow,
):
    client, sql, admin, mailer = account_flow()
    response = client.post(
        "/api/v1/management/client-accounts", headers=HEADERS, json=PAYLOAD
    )
    assert response.status_code == 201, response.text
    assert response.json()["data"]["account"]["id"] == str(USER_ID)
    assert (
        response.json()["data"]["credentials"]["password"]
        == admin.users[TARGET_AUTH_ID]
    )
    assert len(mailer.deliveries) == 1
    assert_existing_account_recovery(client, sql, admin)


def test_unavailable_readback_is_truthful_and_keeps_existing_account_recovery(
    account_flow,
):
    client, sql, admin, mailer = account_flow(fail_readback=True)
    response = client.post(
        "/api/v1/management/client-accounts", headers=HEADERS, json=PAYLOAD
    )
    assert response.status_code == 503
    assert TARGET_AUTH_ID in admin.users
    assert not admin.deletes and not mailer.deliveries
    assert "unknown" in response.json()["detail"].lower()
    assert "password reset" in response.json()["detail"].lower()
    assert "No active SPINA account was created" not in response.text
    assert response.headers["cache-control"] == "no-store"
    sql.fail_readback = False
    assert_existing_account_recovery(client, sql, admin)


@pytest.mark.parametrize(
    "mismatch", ["auth", "borrower", "username", "email", "status", "role"]
)
def test_readback_never_confirms_a_different_or_inactive_identity(
    account_flow, mismatch, monkeypatch
):
    client, sql, admin, mailer = account_flow()
    original_connect = sql.connect

    @contextmanager
    def changed_readback():
        if sql.committed:
            if mismatch == "borrower":
                sql.borrower_user_id = None
            else:
                field, value = {
                    "auth": ("external_auth_id", OTHER_AUTH_ID),
                    "username": ("username", "another.username"),
                    "email": ("email", "other@example.com"),
                    "status": ("status", "suspended"),
                    "role": ("roles", ["employee"]),
                }[mismatch]
                sql.account[field] = value
        with original_connect() as connection:
            yield connection

    # The boundary changes only after the original transaction has committed.
    monkeypatch.setattr(client_account_repository, "open_connection", changed_readback)
    response = client.post(
        "/api/v1/management/client-accounts", headers=HEADERS, json=PAYLOAD
    )
    assert response.status_code == 503
    assert TARGET_AUTH_ID in admin.users and not admin.deletes
    assert "credentials" not in response.json() and not mailer.deliveries


def test_definite_precheck_rejection_creates_or_deletes_no_auth_identity(account_flow):
    client, sql, admin, _ = account_flow()
    sql.borrower_user_id = USER_ID
    response = client.post(
        "/api/v1/management/client-accounts", headers=HEADERS, json=PAYLOAD
    )
    assert response.status_code == 409
    assert admin.creates == 0 and not admin.deletes and not sql.committed


def test_confirmed_domain_rollback_still_compensates_new_identity(account_flow):
    client, sql, admin, mailer = account_flow(reject_link=True)
    response = client.post(
        "/api/v1/management/client-accounts", headers=HEADERS, json=PAYLOAD
    )
    assert response.status_code == 409
    assert not sql.committed and sql.account is None and sql.borrower_user_id is None
    assert not admin.users and admin.deletes == [TARGET_AUTH_ID]
    assert not mailer.deliveries


def test_ordinary_manual_creation_keeps_account_and_recovery(account_flow):
    client, sql, admin, _ = account_flow(lose_ack=False)
    response = client.post(
        "/api/v1/management/client-accounts", headers=HEADERS, json=PAYLOAD
    )
    assert response.status_code == 201
    assert_existing_account_recovery(client, sql, admin)
