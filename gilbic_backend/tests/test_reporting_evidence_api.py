"""Only current Management can retain exact, explicitly reviewed report evidence."""

from dataclasses import replace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from gilbic_backend.auth_api import (
    account_repository_dependency,
    auth_client_dependency,
)
from gilbic_backend.reporting_evidence_api import (
    create_reporting_evidence_router,
    reporting_evidence_repository_dependency,
)
from test_financial_statements import (
    MANAGEMENT_USER_ID,
    FakeAccounts,
    FakeAuthClient,
    headers,
)


class Accounts(FakeAccounts):
    def __init__(self, *, can_manage=True, role="management"):
        super().__init__(role=role)
        self.can_manage = can_manage

    def get_context_for_device(self, **kwargs):
        context = super().get_context_for_device(**kwargs)
        return replace(
            context,
            permissions=("accounting.view", "accounting.journal.manage")
            if self.can_manage
            else ("accounting.view",),
        )


class Evidence:
    def __init__(self):
        self.writes = []

    def retain_policy(self, **values):
        self.writes.append(values)
        return values["request_id"]

    def retain_classification(self, **values):
        self.writes.append(values)
        return values["request_id"]

    def load_policy(self, **_kwargs):
        return None


def client(*, can_manage=True, role="management"):
    app = FastAPI()
    app.include_router(create_reporting_evidence_router())
    repo = Evidence()
    app.dependency_overrides[auth_client_dependency] = FakeAuthClient
    app.dependency_overrides[account_repository_dependency] = lambda: Accounts(
        can_manage=can_manage, role=role
    )
    app.dependency_overrides[reporting_evidence_repository_dependency] = lambda: repo
    return TestClient(app), repo


def body():
    return {
        "request_id": str(uuid4()),
        "book_id": str(uuid4()),
        "policy_id": str(uuid4()),
        "journal_line_id": str(uuid4()),
        "expected_version": 0,
        "expected_amount": "-100.00",
        "allocations": [{"category": "operating", "amount": "-100.00"}],
        "evidence_reference": "test:reviewed-cash-flow",
        "evidence_digest": "a" * 64,
        "reviewed": True,
    }


@pytest.mark.parametrize("prefix", ["/api/v1", "/api/mobile/v1"])
def test_exact_review_keeps_signed_amount_and_server_actor(prefix):
    api, repo = client()
    request = body()
    response = api.post(
        prefix
        + "/management/financial-accounting/statements/cash-flow-classifications",
        headers=headers(),
        json=request,
    )
    assert response.status_code == 200
    assert response.json()["data"]["classification_id"] == request["request_id"]
    assert repo.writes[0]["actor_user_id"] == MANAGEMENT_USER_ID
    assert repo.writes[0]["payload"]["allocations"][0]["amount"] == "-100.00"


@pytest.mark.parametrize(
    "change",
    [
        {"expected_amount": -100.0},
        {"expected_version": True},
        {"actor_user_id": str(uuid4())},
        {"allocations": [{"category": "revenue", "amount": "100.00"}]},
    ],
)
def test_invalid_coordinates_never_reach_repository(change):
    api, repo = client()
    response = api.post(
        "/api/v1/management/financial-accounting/statements/cash-flow-classifications",
        headers=headers(),
        json=body() | change,
    )
    assert response.status_code == 422
    assert not repo.writes


@pytest.mark.parametrize(
    ("can_manage", "role", "reviewed", "status"),
    [
        (False, "management", True, 403),
        (True, "collector", True, 403),
        (True, "management", False, 409),
    ],
)
def test_permission_and_explicit_review_required(can_manage, role, reviewed, status):
    api, repo = client(can_manage=can_manage, role=role)
    response = api.post(
        "/api/v1/management/financial-accounting/statements/cash-flow-classifications",
        headers=headers(),
        json=body() | {"reviewed": reviewed},
    )
    assert response.status_code == status
    assert not repo.writes
