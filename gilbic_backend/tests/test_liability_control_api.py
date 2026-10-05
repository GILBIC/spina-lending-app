"""API boundary preserves actor, exact money, review and immutable source facts."""

from importlib import import_module
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from gilbic_backend.auth_api import (
    account_repository_dependency,
    auth_client_dependency,
)
from test_accounting_book_api import ACTOR, HEADERS, FakeAccounts, FakeAuth

PATH = "/api/v1/management/financial-accounting/liabilities"
BOOK, REQUEST, LINE, OBLIGATION = [str(uuid4()) for _ in range(4)]
BODY = {
    "request_id": REQUEST,
    "expected_book_id": BOOK,
    "kind": "borrowing_owner",
    "counterparty": "Synthetic owner lender",
    "due_date": "2050-10-01",
    "journal_line_id": LINE,
    "expected_account_code": "2310",
    "expected_amount": "100.00",
    "expected_posting_date": "2050-01-01",
    "expected_source_type": "manual",
    "expected_source_reference": None,
    "evidence_reference": "test:loan-contract",
    "evidence_digest": "a" * 64,
    "reviewed": True,
}


class MemorySchedule:
    def __init__(self):
        self.reads, self.writes = [], []

    def load_schedule(self, **values):
        self.reads.append(values)
        return {
            "book": {"status": "configured", "book_id": BOOK},
            "obligations": [],
            "reconciliation": [],
            "unregistered_lines": [],
        }

    def register_obligation(self, **values):
        self.writes.append(values)
        return OBLIGATION

    def record_movement(self, **values):
        self.writes.append(values)
        return REQUEST


def client_for(repo, accounts=None):
    try:
        api = import_module("gilbic_backend.liability_control_api")
    except ModuleNotFoundError:
        pytest.fail("The protected liability API is not implemented")
    app = FastAPI()
    app.include_router(api.create_liability_control_router())
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuth()
    app.dependency_overrides[account_repository_dependency] = lambda: (
        accounts or FakeAccounts()
    )
    app.dependency_overrides[api.liability_control_repository_dependency] = lambda: repo
    return TestClient(app)


def test_registration_uses_authenticated_actor_and_exact_reviewed_source():
    repo = MemorySchedule()
    with client_for(repo) as client:
        response = client.post(PATH, headers=HEADERS, json=BODY)
    assert response.status_code == 200
    assert response.json()["data"]["obligation_id"] == OBLIGATION
    assert repo.writes[0]["actor_user_id"] == ACTOR
    assert repo.writes[0]["payload"]["expected_amount"] == "100.00"
    assert repo.writes[0]["payload"]["kind"] == "borrowing_owner"


@pytest.mark.parametrize(
    "change,expected",
    [
        ({"reviewed": False}, 409),
        ({"reviewed": "true"}, 422),
        ({"expected_amount": 100}, 422),
        ({"expected_amount": "100.001"}, 422),
        ({"expected_amount": "0.00"}, 422),
        ({"expected_account_code": "2100"}, 422),
        ({"actor_user_id": REQUEST}, 422),
        ({"database_url": "untrusted"}, 422),
        ({"evidence_reference": " ref "}, 422),
        ({"counterparty": "\t"}, 422),
    ],
)
def test_invalid_or_unreviewed_write_never_reaches_repository(change, expected):
    repo = MemorySchedule()
    with client_for(repo) as client:
        response = client.post(PATH, headers=HEADERS, json=BODY | change)
    assert response.status_code == expected
    assert repo.writes == []


@pytest.mark.parametrize(
    "role,permissions",
    [("client", ("accounting.view", "accounting.journal.manage")), ("management", ())],
)
def test_unauthorized_actor_never_reads_or_registers(role, permissions):
    repo = MemorySchedule()
    with client_for(repo, FakeAccounts(role=role, permissions=permissions)) as client:
        assert client.get(PATH, headers=HEADERS).status_code == 403
        assert client.post(PATH, headers=HEADERS, json=BODY).status_code == 403
    assert repo.reads == repo.writes == []


def test_view_only_manager_reads_as_of_schedule_but_cannot_write():
    repo = MemorySchedule()
    with client_for(repo, FakeAccounts(permissions=("accounting.view",))) as client:
        assert (
            client.get(PATH + "?as_of=2050-06-30", headers=HEADERS).status_code == 200
        )
        assert client.post(PATH, headers=HEADERS, json=BODY).status_code == 403
    assert str(repo.reads[0]["as_of"]) == "2050-06-30"
    assert repo.reads[0]["actor_user_id"] == ACTOR


def test_mobile_read_has_same_authorization_and_schedule_contract():
    repo = MemorySchedule()
    with client_for(repo) as client:
        response = client.get(
            PATH.replace("/api/v1/", "/api/mobile/v1/"), headers=HEADERS
        )
    assert response.status_code == 200
    assert response.json()["data"]["book"]["book_id"] == BOOK


def test_missing_authentication_never_returns_liability_evidence():
    repo = MemorySchedule()
    with client_for(repo) as client:
        assert client.get(PATH).status_code == 401
    assert repo.reads == []


def test_movement_binds_route_obligation_and_requires_reversal_reference():
    repo = MemorySchedule()
    payload = {
        key: value
        for key, value in BODY.items()
        if key not in {"counterparty", "due_date"}
    }
    payload.update(kind="reversal", reverses_claim_id=LINE)
    with client_for(repo) as client:
        assert (
            client.post(
                PATH + f"/{OBLIGATION}/movements", headers=HEADERS, json=payload
            ).status_code
            == 200
        )
        assert repo.writes[0]["payload"]["obligation_id"] == OBLIGATION
        assert (
            client.post(
                PATH + f"/{OBLIGATION}/movements",
                headers=HEADERS,
                json=payload | {"reverses_claim_id": None},
            ).status_code
            == 422
        )
