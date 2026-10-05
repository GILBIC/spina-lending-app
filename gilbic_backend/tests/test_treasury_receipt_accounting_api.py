from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from gilbic_backend.auth_api import (
    account_repository_dependency,
    auth_client_dependency,
)
from gilbic_backend.treasury_authorization import TreasuryConflict, TreasuryDenied
from gilbic_backend.treasury_receipt_accounting_api import (
    create_treasury_receipt_accounting_router,
    treasury_receipt_accounting_repository_dependency,
)
from test_accounting_book_api import ACTOR, HEADERS, FakeAccounts, FakeAuth

BASE = "/api/v1/management/financial-accounting/treasury"
RECEIPT, MAPPING, PREPARATION, WALLET, REQUEST = (uuid4() for _ in range(5))


class MemoryReceipts:
    def __init__(self):
        self.calls = []
        self.error = None

    def invoke(self, name, actor, **values):
        self.calls.append((name, actor.user_id, values))
        if self.error:
            raise self.error
        return {"amount": "147.25", "id": str(PREPARATION)}

    def read_mapping(self, actor, **values):
        return self.invoke("read_mapping", actor, **values)

    def configure_mapping(self, actor, **values):
        return self.invoke("configure_mapping", actor, **values)

    def review(self, actor, **values):
        return self.invoke("review", actor, **values)

    def prepare(self, actor, **values):
        return self.invoke("prepare", actor, **values)

    def read_preparation(self, actor, **values):
        return self.invoke("read_preparation", actor, **values)

    def post(self, actor, **values):
        return self.invoke("post", actor, **values)


def client_for(accounts=None, repository=None):
    repository = repository or MemoryReceipts()
    app = FastAPI()
    app.include_router(create_treasury_receipt_accounting_router())
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuth()
    app.dependency_overrides[account_repository_dependency] = lambda: (
        accounts or FakeAccounts()
    )
    app.dependency_overrides[treasury_receipt_accounting_repository_dependency] = (
        lambda: repository
    )
    return TestClient(app), repository


def test_review_requires_authentication_and_does_not_call_repository():
    client, repo = client_for()
    response = client.get(
        f"{BASE}/receipts/{RECEIPT}/review", params={"mapping_id": str(MAPPING)}
    )
    assert response.status_code == 401
    assert repo.calls == []


@pytest.mark.parametrize(
    "accounts",
    [
        FakeAccounts(role="collector"),
        FakeAccounts(permissions=("accounting.view",)),
        FakeAccounts(status="inactive"),
    ],
)
def test_review_requires_active_management_accounting_authority(accounts):
    client, repo = client_for(accounts)
    response = client.get(
        f"{BASE}/receipts/{RECEIPT}/review",
        params={"mapping_id": str(MAPPING)},
        headers=HEADERS,
    )
    assert response.status_code == 403
    assert repo.calls == []


def test_review_private_response_preserves_exact_decimal_string():
    client, repo = client_for()
    response = client.get(
        f"{BASE}/receipts/{RECEIPT}/review",
        params={"mapping_id": str(MAPPING)},
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["data"]["amount"] == "147.25"
    assert response.headers["cache-control"] == "no-store"
    assert repo.calls == [
        ("review", ACTOR, {"receipt_id": RECEIPT, "mapping_id": MAPPING})
    ]


def test_mapping_requires_explicit_confirmation_without_sending_actor_from_client():
    client, repo = client_for()
    body = {
        "cash_code": "1030",
        "expected_version": 0,
        "request_id": str(REQUEST),
        "evidence_reference": "test:review",
        "evidence_digest": "c" * 64,
    }
    assert (
        client.post(
            f"{BASE}/accounts/{WALLET}/cash-mapping", json=body, headers=HEADERS
        ).status_code
        == 409
    )
    assert repo.calls == []
    body["confirm"] = True
    response = client.post(
        f"{BASE}/accounts/{WALLET}/cash-mapping", json=body, headers=HEADERS
    )
    assert response.status_code == 200
    assert repo.calls[0][1] == ACTOR
    assert repo.calls[0][2]["expected_version"] == 0


@pytest.mark.parametrize(
    "extra",
    [{"amount": "1.00"}, {"actor_user_id": str(uuid4())}, {"cash_code": "1010"}],
)
def test_post_forbids_arbitrary_journal_or_actor_inputs(extra):
    client, repo = client_for()
    body = dict(
        source_digest="a" * 64, confirmation_token="b" * 64, confirm=True, **extra
    )
    response = client.post(
        f"{BASE}/receipt-preparations/{PREPARATION}/post", json=body, headers=HEADERS
    )
    assert response.status_code == 422
    assert repo.calls == []


@pytest.mark.parametrize("confirm", [False, "true", 1])
def test_post_confirmation_is_explicit_boolean(confirm):
    client, repo = client_for()
    response = client.post(
        f"{BASE}/receipt-preparations/{PREPARATION}/post",
        json={
            "source_digest": "a" * 64,
            "confirmation_token": "b" * 64,
            "confirm": confirm,
        },
        headers=HEADERS,
    )
    assert response.status_code in {409, 422}
    assert repo.calls == []


@pytest.mark.parametrize(
    "error,status",
    [
        (TreasuryDenied("Current private permission required"), 403),
        (TreasuryConflict("Receipt evidence stale"), 409),
    ],
)
def test_current_repository_rejection_reaches_caller(error, status):
    repo = MemoryReceipts()
    repo.error = error
    client, _ = client_for(repository=repo)
    response = client.post(
        f"{BASE}/receipt-preparations/{PREPARATION}/post",
        json={
            "source_digest": "a" * 64,
            "confirmation_token": "b" * 64,
            "confirm": True,
        },
        headers=HEADERS,
    )
    assert response.status_code == status


def test_prepare_pins_source_and_mobile_contract_matches_web():
    client, repo = client_for()
    response = client.post(
        f"{BASE.replace('/api/v1/', '/api/mobile/v1/')}/receipts/{RECEIPT}/prepare",
        json={
            "mapping_id": str(MAPPING),
            "source_digest": "a" * 64,
            "request_id": str(REQUEST),
        },
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert repo.calls == [
        (
            "prepare",
            ACTOR,
            {
                "receipt_id": RECEIPT,
                "mapping_id": MAPPING,
                "source_digest": "a" * 64,
                "request_id": REQUEST,
            },
        )
    ]
