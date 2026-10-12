"""Private application review accepts identities, never client journal amounts."""

from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from gilbic_backend.auth_api import (
    account_repository_dependency,
    auth_client_dependency,
)
from gilbic_backend.treasury_application_accounting_api import (
    create_treasury_application_accounting_router,
    treasury_application_accounting_repository_dependency,
)
from gilbic_backend.treasury_authorization import TreasuryConflict, TreasuryDenied
from test_accounting_book_api import ACTOR, HEADERS, FakeAccounts, FakeAuth

BASE = "/api/v1/management/financial-accounting/treasury"
APPLICATION, PREPARATION, REQUEST = (uuid4() for _ in range(3))


class MemoryApplications:
    def __init__(self):
        self.calls = []
        self.error = None

    def invoke(self, method, actor, **values):
        self.calls.append((method, actor.user_id, values))
        if self.error:
            raise self.error
        return {"amount": "50.00", "id": str(PREPARATION)}

    def review(self, actor, **values):
        return self.invoke("review", actor, **values)

    def prepare(self, actor, **values):
        return self.invoke("prepare", actor, **values)

    def read_preparation(self, actor, **values):
        return self.invoke("read_preparation", actor, **values)

    def post(self, actor, **values):
        return self.invoke("post", actor, **values)


def client_for(accounts=None, repository=None):
    repository = repository or MemoryApplications()
    app = FastAPI()
    app.include_router(create_treasury_application_accounting_router())
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuth()
    app.dependency_overrides[account_repository_dependency] = lambda: (
        accounts or FakeAccounts()
    )
    app.dependency_overrides[treasury_application_accounting_repository_dependency] = (
        lambda: repository
    )
    return TestClient(app), repository


def test_review_requires_authentication():
    client, repo = client_for()
    assert client.get(f"{BASE}/applications/{APPLICATION}/review").status_code == 401
    assert repo.calls == []


@pytest.mark.parametrize(
    "accounts",
    [
        FakeAccounts(role="collector"),
        FakeAccounts(permissions=("accounting.view",)),
        FakeAccounts(status="inactive"),
    ],
)
def test_current_management_accounting_authority_required(accounts):
    client, repo = client_for(accounts)
    assert (
        client.get(
            f"{BASE}/applications/{APPLICATION}/review", headers=HEADERS
        ).status_code
        == 403
    )
    assert repo.calls == []


def test_review_is_private_and_decimal_exact():
    client, repo = client_for()
    response = client.get(f"{BASE}/applications/{APPLICATION}/review", headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["data"]["amount"] == "50.00"
    assert response.headers["cache-control"] == "no-store"
    assert repo.calls == [("review", ACTOR, {"application_id": APPLICATION})]


@pytest.mark.parametrize(
    "extra",
    [
        {"amount": "1.00"},
        {"account_code": "1020"},
        {"actor_user_id": str(uuid4())},
        {"loan_id": str(uuid4())},
    ],
)
def test_post_forbids_arbitrary_financial_or_actor_inputs(extra):
    client, repo = client_for()
    response = client.post(
        f"{BASE}/application-preparations/{PREPARATION}/post",
        headers=HEADERS,
        json=dict(
            source_digest="a" * 64, confirmation_token="b" * 64, confirm=True, **extra
        ),
    )
    assert response.status_code == 422
    assert repo.calls == []


@pytest.mark.parametrize("confirm", [False, "true", 1])
def test_post_requires_explicit_boolean_confirmation(confirm):
    client, repo = client_for()
    response = client.post(
        f"{BASE}/application-preparations/{PREPARATION}/post",
        headers=HEADERS,
        json={
            "source_digest": "a" * 64,
            "confirmation_token": "b" * 64,
            "confirm": confirm,
        },
    )
    assert response.status_code in {409, 422}
    assert repo.calls == []


@pytest.mark.parametrize(
    "error,status",
    [
        (TreasuryDenied("Current private permission required"), 403),
        (TreasuryConflict("Prior ledger changed"), 409),
    ],
)
def test_repository_rejection_reaches_caller(error, status):
    repo = MemoryApplications()
    repo.error = error
    client, _ = client_for(repository=repo)
    response = client.post(
        f"{BASE}/application-preparations/{PREPARATION}/post",
        headers=HEADERS,
        json={
            "source_digest": "a" * 64,
            "confirmation_token": "b" * 64,
            "confirm": True,
        },
    )
    assert response.status_code == status


def test_mobile_prepare_pins_source_digest():
    client, repo = client_for()
    response = client.post(
        f"{BASE.replace('/api/v1/', '/api/mobile/v1/')}/applications/{APPLICATION}/prepare",
        headers=HEADERS,
        json={"source_digest": "a" * 64, "request_id": str(REQUEST)},
    )
    assert response.status_code == 200
    assert repo.calls == [
        (
            "prepare",
            ACTOR,
            {
                "application_id": APPLICATION,
                "source_digest": "a" * 64,
                "request_id": REQUEST,
            },
        )
    ]
