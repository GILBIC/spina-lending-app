from contextlib import contextmanager
from dataclasses import replace
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from gilbic_backend.account_repository import DeviceRevoked
from gilbic_backend.auth_api import (
    account_repository_dependency,
    auth_client_dependency,
)
from test_renewal_api import CLIENT_USER_ID, REQUEST_ID, FakeAccounts, FakeAuthClient

from gilbic_backend import renewal_workflow_api as workflow

RECOMMEND = "renewal.recommend.assigned"
CUSTODY = "renewal.cash_custody.assigned"
HEADERS = {"Authorization": "Bearer test-token", "X-Device-Id": "test-device"}
PREFIXES = ["/api/v1", "/api/mobile/v1"]


class QueueDatabase:
    def __init__(self):
        self.calls = []

    @contextmanager
    def open(self):
        yield self

    @contextmanager
    def cursor(self, **kwargs):
        yield self

    def execute(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))

    def fetchall(self):
        return []


def make_client(monkeypatch, permissions, *, revoked=False):
    class Accounts(FakeAccounts):
        def get_context_for_device(self, **kwargs):
            if revoked:
                raise DeviceRevoked("This device is revoked.")
            return replace(
                super().get_context_for_device(**kwargs),
                roles=("collector",),
                permissions=tuple(permissions),
            )

    database = QueueDatabase()
    monkeypatch.setattr(workflow, "open_connection", database.open)
    app = FastAPI()
    app.include_router(workflow.create_renewal_workflow_router())
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: Accounts(
        role="collector"
    )
    return TestClient(app), database


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize(
    "permissions", [(RECOMMEND,), (CUSTODY,), (RECOMMEND, CUSTODY)]
)
def test_either_assigned_permission_reads_only_the_actors_queue(
    monkeypatch, prefix, permissions
):
    client, database = make_client(monkeypatch, permissions)
    response = client.get(f"{prefix}/collector/renewals", headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["data"] == {"requests": []}
    assert len(database.calls) == 1
    sql, params = database.calls[0]
    assert "where lending.collector_area_owner(client.area) = %s" in sql
    assert params == (CLIENT_USER_ID,)


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("permissions", [(), ("renewal.manage",)])
def test_queue_denies_without_either_assigned_permission(
    monkeypatch, prefix, permissions
):
    client, database = make_client(monkeypatch, permissions)
    assert (
        client.get(f"{prefix}/collector/renewals", headers=HEADERS).status_code == 403
    )
    assert database.calls == []


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize(
    "headers,revoked,status",
    [
        ({"X-Device-Id": "test-device"}, False, 401),
        ({"Authorization": "Bearer test-token"}, False, 400),
        (HEADERS, True, 403),
    ],
)
def test_custody_queue_preserves_authentication_and_device_checks(
    monkeypatch, prefix, headers, revoked, status
):
    client, database = make_client(monkeypatch, (CUSTODY,), revoked=revoked)
    assert (
        client.get(f"{prefix}/collector/renewals", headers=headers).status_code
        == status
    )
    assert database.calls == []


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize(
    "permission,action",
    [
        (CUSTODY, "recommendation"),
        (RECOMMEND, "cash-received"),
        (RECOMMEND, "cash-given"),
        (RECOMMEND, "handover-photo"),
    ],
)
def test_shared_queue_access_does_not_grant_the_other_write_permission(
    monkeypatch, prefix, permission, action
):
    client, database = make_client(monkeypatch, (permission,))
    response = client.post(
        f"{prefix}/collector/renewals/{REQUEST_ID}/{action}",
        headers=HEADERS,
        json={"recommendation": "recommend", "reason_code": "Good payment history"},
    )
    assert response.status_code == 403
    assert database.calls == []


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("action", ["cash-received", "cash-given", "handover-photo"])
def test_custody_does_not_authorize_another_collectors_renewal(
    monkeypatch, prefix, action
):
    client, database = make_client(monkeypatch, (CUSTODY,))
    monkeypatch.setattr(
        workflow,
        "_renewal_row",
        lambda *args, **kwargs: {"assigned_collector_user_id": UUID(int=999)},
    )
    response = client.post(
        f"{prefix}/collector/renewals/{REQUEST_ID}/{action}",
        headers={**HEADERS, "Content-Type": "image/jpeg"},
        content=b"synthetic-photo",
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "renewal_assigned_collector_required"
    assert database.calls == []
