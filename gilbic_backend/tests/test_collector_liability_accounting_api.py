from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from gilbic_backend.auth_api import (
    account_repository_dependency,
    auth_client_dependency,
)
from gilbic_backend.collector_liability_accounting_api import (
    collector_liability_accounting_repository_dependency,
    create_collector_liability_accounting_router,
)
from test_accounting_book_api import ACTOR, HEADERS, FakeAccounts, FakeAuth

BASE = "/api/v1/management/financial-accounting/collector"
SOURCE, PREPARATION, REQUEST = (uuid4() for _ in range(3))


class Repository:
    def __init__(self):
        self.calls = []

    def invoke(self, method, actor, **values):
        self.calls.append((method, actor.user_id, values))
        return {"amount": "10.00", "fee": "0.00"}

    def review(self, actor, **values):
        return self.invoke("review", actor, **values)

    def prepare(self, actor, **values):
        return self.invoke("prepare", actor, **values)

    def read_preparation(self, actor, **values):
        return self.invoke("read_preparation", actor, **values)

    def post(self, actor, **values):
        return self.invoke("post", actor, **values)


def client_for(accounts=None):
    repo = Repository()
    app = FastAPI()
    app.include_router(create_collector_liability_accounting_router())
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuth()
    app.dependency_overrides[account_repository_dependency] = lambda: (
        accounts or FakeAccounts()
    )
    app.dependency_overrides[collector_liability_accounting_repository_dependency] = (
        lambda: repo
    )
    return TestClient(app), repo


@pytest.mark.parametrize(
    "accounts",
    [
        FakeAccounts(role="collector"),
        FakeAccounts(permissions=("accounting.view",)),
        FakeAccounts(status="inactive"),
    ],
)
def test_review_requires_current_management_and_accounting_authority(accounts):
    client, repo = client_for(accounts)
    assert (
        client.get(f"{BASE}/settlement/{SOURCE}/review", headers=HEADERS).status_code
        == 403
    )
    assert repo.calls == []


def test_review_is_private_and_identifies_exact_source():
    client, repo = client_for()
    assert client.get(f"{BASE}/settlement/{SOURCE}/review").status_code == 401
    result = client.get(f"{BASE}/settlement/{SOURCE}/review", headers=HEADERS)
    assert result.status_code == 200 and result.headers["cache-control"] == "no-store"
    assert repo.calls == [
        ("review", ACTOR, {"source_kind": "settlement", "source_id": SOURCE})
    ]


@pytest.mark.parametrize("kind", ["opening", "reservation", "correction"])
def test_unsupported_family_cannot_be_posted_as_supported(kind):
    client, repo = client_for()
    assert (
        client.get(f"{BASE}/{kind}/{SOURCE}/review", headers=HEADERS).status_code == 422
    )
    assert repo.calls == []


@pytest.mark.parametrize(
    "extra",
    [{"amount": "1.00"}, {"account_code": "2220"}, {"actor_user_id": str(uuid4())}],
)
def test_client_cannot_supply_journal_coordinates(extra):
    client, repo = client_for()
    response = client.post(
        f"{BASE}/preparations/{PREPARATION}/post",
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
def test_post_requires_explicit_exact_boolean_confirmation(confirm):
    client, repo = client_for()
    response = client.post(
        f"{BASE}/preparations/{PREPARATION}/post",
        headers=HEADERS,
        json={
            "source_digest": "a" * 64,
            "confirmation_token": "b" * 64,
            "confirm": confirm,
        },
    )
    assert response.status_code in (409, 422) and repo.calls == []


def test_mobile_prepare_retains_exact_request_identity():
    client, repo = client_for()
    response = client.post(
        f"{BASE.replace('/api/v1/', '/api/mobile/v1/')}/recognition/{SOURCE}/prepare",
        headers=HEADERS,
        json={"source_digest": "a" * 64, "request_id": str(REQUEST)},
    )
    assert response.status_code == 200
    assert repo.calls == [
        (
            "prepare",
            ACTOR,
            {
                "source_kind": "recognition",
                "source_id": SOURCE,
                "source_digest": "a" * 64,
                "request_id": REQUEST,
            },
        )
    ]
