from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from gilbic_backend.auth_api import (
    account_repository_dependency,
    auth_client_dependency,
)
from gilbic_backend.loan_payout_accounting_api import (
    create_loan_payout_accounting_router,
    loan_payout_accounting_repository_dependency,
)
from gilbic_backend.treasury_authorization import TreasuryConflict, TreasuryDenied
from test_accounting_book_api import ACTOR, HEADERS, FakeAccounts, FakeAuth

BASE = "/api/v1/management/financial-accounting/treasury"
PAYOUT, PREPARATION, REQUEST = (uuid4() for _ in range(3))
PARAMS = {"stage": "debit"}


class MemoryPayouts:
    def __init__(self):
        self.calls = []
        self.error = None

    def invoke(self, method, actor, **values):
        self.calls.append((method, actor.user_id, values))
        if self.error:
            raise self.error
        return {"amount": "100.00", "fee": "2.00"}

    def review(self, actor, **values):
        return self.invoke("review", actor, **values)

    def prepare(self, actor, **values):
        return self.invoke("prepare", actor, **values)

    def read_preparation(self, actor, **values):
        return self.invoke("read_preparation", actor, **values)

    def post(self, actor, **values):
        return self.invoke("post", actor, **values)


def client_for(accounts=None, repository=None):
    repository = repository or MemoryPayouts()
    app = FastAPI()
    app.include_router(create_loan_payout_accounting_router())
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuth()
    app.dependency_overrides[account_repository_dependency] = lambda: (
        accounts or FakeAccounts()
    )
    app.dependency_overrides[loan_payout_accounting_repository_dependency] = lambda: (
        repository
    )
    return TestClient(app), repository


def test_payout_review_requires_authentication():
    client, repo = client_for()
    assert (
        client.get(f"{BASE}/payouts/{PAYOUT}/review", params=PARAMS).status_code == 401
    )
    assert repo.calls == []


@pytest.mark.parametrize(
    "accounts",
    [
        FakeAccounts(role="collector"),
        FakeAccounts(permissions=("accounting.view",)),
        FakeAccounts(status="inactive"),
    ],
)
def test_payout_review_requires_current_management_accounting_permission(accounts):
    client, repo = client_for(accounts)
    assert (
        client.get(
            f"{BASE}/payouts/{PAYOUT}/review", params=PARAMS, headers=HEADERS
        ).status_code
        == 403
    )
    assert repo.calls == []


def test_payout_review_pins_actual_stage():
    client, repo = client_for()
    response = client.get(
        f"{BASE}/payouts/{PAYOUT}/review", params=PARAMS, headers=HEADERS
    )
    assert (
        response.status_code == 200 and response.headers["cache-control"] == "no-store"
    )
    assert response.json()["data"] == {"amount": "100.00", "fee": "2.00"}
    assert repo.calls == [
        (
            "review",
            ACTOR,
            {
                "payout_id": PAYOUT,
                "stage": "debit",
            },
        )
    ]


@pytest.mark.parametrize(
    "extra",
    [
        {"amount": "1.00"},
        {"fee": "0.00"},
        {"actor_user_id": str(uuid4())},
        {"account_code": "1050"},
    ],
)
def test_payout_post_forbids_money_or_actor_from_client(extra):
    client, repo = client_for()
    response = client.post(
        f"{BASE}/payout-preparations/{PREPARATION}/post",
        headers=HEADERS,
        json={
            "source_digest": "a" * 64,
            "confirmation_token": "b" * 64,
            "confirm": True,
            **extra,
        },
    )
    assert response.status_code == 422 and repo.calls == []


@pytest.mark.parametrize("confirm", [False, "true", 1])
def test_payout_post_requires_explicit_boolean_confirmation(confirm):
    client, repo = client_for()
    response = client.post(
        f"{BASE}/payout-preparations/{PREPARATION}/post",
        headers=HEADERS,
        json={
            "source_digest": "a" * 64,
            "confirmation_token": "b" * 64,
            "confirm": confirm,
        },
    )
    assert response.status_code in {409, 422} and repo.calls == []


@pytest.mark.parametrize(
    "error,status",
    [
        (TreasuryDenied("Private wallet required"), 403),
        (TreasuryConflict("Actual payout evidence stale"), 409),
    ],
)
def test_payout_repository_rejection_reaches_caller(error, status):
    repo = MemoryPayouts()
    repo.error = error
    client, _ = client_for(repository=repo)
    assert (
        client.get(
            f"{BASE}/payouts/{PAYOUT}/review", params=PARAMS, headers=HEADERS
        ).status_code
        == status
    )


def test_mobile_payout_prepare_uses_same_explicit_review_contract():
    client, repo = client_for()
    response = client.post(
        f"{BASE.replace('/api/v1/', '/api/mobile/v1/')}/payouts/{PAYOUT}/prepare",
        headers=HEADERS,
        json={**PARAMS, "source_digest": "a" * 64, "request_id": str(REQUEST)},
    )
    assert response.status_code == 200
    assert repo.calls[0][2]["request_id"] == REQUEST
