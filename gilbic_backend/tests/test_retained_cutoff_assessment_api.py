"""Management-only dated assessment, exact digest and explicit confirmation."""

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

BOOK, PERIOD, LOAN, PREPARATION, CONFIRMATION = [str(uuid4()) for _ in range(5)]
BASE = "/api/v1/management/financial-accounting/period-assessments"
PATH = BASE + f"/{PERIOD}/loans/{LOAN}"
PERMISSIONS = (
    "accounting.view",
    "accounting.period.close.prepare",
    "accounting.period.close.post",
)
BODY = {
    "expected_book_id": BOOK,
    "source_digest": "a" * 64,
    "review_rationale": "Reviewed exact cutoff release and protected dated ECL evidence.",
}


class MemoryAssessments:
    def __init__(self):
        self.reads, self.writes = [], []

    def load_candidate(self, **values):
        self.reads.append(values)
        return {
            "ready": True,
            "source_digest": "a" * 64,
            "comprehensive_source_coverage": False,
        }

    def prepare(self, **values):
        self.writes.append(values)
        return PREPARATION

    def confirm(self, **values):
        self.writes.append(values)
        return CONFIRMATION


def client_for(repo, accounts=None):
    try:
        api = import_module("gilbic_backend.retained_cutoff_assessment_api")
    except ModuleNotFoundError:
        pytest.fail("The retained cutoff assessment API is not implemented")
    app = FastAPI()
    app.include_router(api.create_retained_cutoff_assessment_router())
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuth()
    app.dependency_overrides[account_repository_dependency] = lambda: (
        accounts or FakeAccounts(permissions=PERMISSIONS)
    )
    app.dependency_overrides[api.retained_cutoff_assessment_repository_dependency] = (
        lambda: repo
    )
    return TestClient(app)


def test_assessment_candidate_and_prepare_use_authenticated_actor_and_route_scope():
    repo = MemoryAssessments()
    with client_for(repo) as client:
        assert client.get(PATH, headers=HEADERS).status_code == 200
        result = client.post(PATH + "/prepare", headers=HEADERS, json=BODY)
    assert result.status_code == 200
    assert result.json()["data"]["preparation_id"] == PREPARATION
    assert repo.reads[0]["actor_user_id"] == ACTOR
    assert str(repo.writes[0]["period_id"]) == PERIOD
    assert str(repo.writes[0]["loan_id"]) == LOAN
    assert repo.writes[0]["actor_user_id"] == ACTOR


@pytest.mark.parametrize(
    "change",
    [
        {"source_digest": "bad"},
        {"review_rationale": "short"},
        {"actor_user_id": BOOK},
        {"measurement_date": "2000-01-01"},
        {"source_snapshot": {}},
    ],
)
def test_client_cannot_supply_measurement_or_forge_source_scope(change):
    repo = MemoryAssessments()
    with client_for(repo) as client:
        assert (
            client.post(
                PATH + "/prepare", headers=HEADERS, json=BODY | change
            ).status_code
            == 422
        )
    assert repo.writes == []


def test_confirm_requires_strict_explicit_confirmation_and_expected_book():
    repo = MemoryAssessments()
    body = {"expected_book_id": BOOK, "source_digest": "a" * 64, "confirm": True}
    with client_for(repo) as client:
        route = BASE + f"/preparations/{PREPARATION}/confirm"
        assert (
            client.post(
                route, headers=HEADERS, json=body | {"confirm": False}
            ).status_code
            == 409
        )
        assert (
            client.post(
                route, headers=HEADERS, json=body | {"confirm": "true"}
            ).status_code
            == 422
        )
        result = client.post(route, headers=HEADERS, json=body)
    assert result.status_code == 200
    assert result.json()["data"]["confirmation_id"] == CONFIRMATION
    assert len(repo.writes) == 1
    assert repo.writes[0]["actor_user_id"] == ACTOR
    assert str(repo.writes[0]["expected_book_id"]) == BOOK


@pytest.mark.parametrize(
    "role,permissions,status",
    [
        ("client", PERMISSIONS, "active"),
        ("management", (), "active"),
        ("management", PERMISSIONS, "inactive"),
    ],
)
def test_unauthorized_actor_never_reads_or_writes(role, permissions, status):
    repo = MemoryAssessments()
    with client_for(
        repo, FakeAccounts(role=role, permissions=permissions, status=status)
    ) as client:
        assert client.get(PATH, headers=HEADERS).status_code == 403
        assert (
            client.post(PATH + "/prepare", headers=HEADERS, json=BODY).status_code
            == 403
        )
    assert repo.reads == repo.writes == []


def test_view_only_manager_can_read_but_cannot_prepare():
    repo = MemoryAssessments()
    with client_for(repo, FakeAccounts(permissions=("accounting.view",))) as client:
        assert client.get(PATH, headers=HEADERS).status_code == 200
        assert (
            client.post(PATH + "/prepare", headers=HEADERS, json=BODY).status_code
            == 403
        )
    assert repo.writes == []


def test_mobile_candidate_has_same_scope_and_authentication():
    repo = MemoryAssessments()
    with client_for(repo) as client:
        assert (
            client.get(
                PATH.replace("/api/v1/", "/api/mobile/v1/"), headers=HEADERS
            ).status_code
            == 200
        )
        assert client.get(PATH).status_code == 401
    assert len(repo.reads) == 1
