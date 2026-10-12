"""Current risk decisions bind the shown source; clients cannot date reviews."""

from copy import deepcopy
from importlib import import_module

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from gilbic_backend.auth_api import (
    account_repository_dependency,
    auth_client_dependency,
)
from test_accounting_book_api import ACTOR, HEADERS, FakeAccounts, FakeAuth
from test_elapsed_period_assessment_api import BASE, BOOK, LOAN, PERIOD

PERMISSIONS = ("accounting.view", "accounting.ecl.credit_risk_label.review")
BODY = {
    "expected_book_id": BOOK,
    "source_digest": "a" * 64,
    "confirm": True,
    "review": {
        "stage_label": "stage_2_lifetime",
        "default_label": False,
        "write_off_label": "none",
        "recovery_label": "none",
        "primary_evidence_basis": "verified_qualitative_credit_event",
        "evidence_reference": "synthetic-risk-evidence",
        "review_note": "Reviewed current protected facts and explicit borrower evidence.",
        "sicr_backstop_rebutted": False,
        "default_backstop_rebutted": False,
    },
}


class MemoryReviews:
    def __init__(self):
        self.reads, self.writes = [], []

    def load_context(self, **values):
        self.reads.append(values)
        return {"ready": True, "source_digest": "a" * 64}

    def retain(self, **values):
        self.writes.append(values)
        return {"review_id": 71, "as_of_date": "2026-10-10"}


def client_for(repo, accounts=None):
    try:
        api = import_module("gilbic_backend.current_credit_risk_review_api")
    except ModuleNotFoundError:
        pytest.fail("Source-bound current risk review API is not implemented")
    app = FastAPI()
    app.include_router(api.create_current_credit_risk_review_router())
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuth()
    app.dependency_overrides[account_repository_dependency] = lambda: (
        accounts or FakeAccounts(permissions=PERMISSIONS)
    )
    app.dependency_overrides[api.current_credit_risk_review_repository_dependency] = (
        lambda: repo
    )
    return TestClient(app)


@pytest.mark.parametrize("base", [BASE, BASE.replace("/api/v1/", "/api/mobile/v1/")])
def test_current_risk_review_binds_actor_source_and_explicit_decision(base):
    repo = MemoryReviews()
    path = base + f"/{PERIOD}/loans/{LOAN}/risk-review"
    with client_for(repo) as client:
        assert client.get(path, headers=HEADERS).status_code == 200
        response = client.post(path, headers=HEADERS, json=BODY)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["data"]["review_id"] == 71
    assert repo.writes[0]["actor_user_id"] == ACTOR
    assert repo.writes[0]["source_digest"] == BODY["source_digest"]
    assert repo.writes[0]["review"]["default_label"] is False


@pytest.mark.parametrize(
    "field,value,status",
    [
        ("confirm", False, 409),
        ("confirm", "true", 422),
        ("source_digest", "invalid", 422),
        ("as_of_date", "2020-01-01", 422),
        ("reviewed_at", "2020-01-01T00:00:00Z", 422),
        ("actor_user_id", BOOK, 422),
        ("days_past_due", 90, 422),
        ("inherited_review", {"id": 71}, 422),
    ],
)
def test_current_review_refuses_client_authority(field, value, status):
    repo = MemoryReviews()
    with client_for(repo) as client:
        response = client.post(
            BASE + f"/{PERIOD}/loans/{LOAN}/risk-review",
            headers=HEADERS,
            json=BODY | {field: value},
        )
    assert response.status_code == status
    assert not repo.writes


@pytest.mark.parametrize(
    "field,value",
    [
        ("default_label", "false"),
        ("sicr_backstop_rebutted", 0),
        ("default_backstop_rebutted", "false"),
        ("as_of_date", "2020-01-01"),
        ("evidence_reference", 23),
    ],
)
def test_review_labels_are_strict_and_have_no_client_date(field, value):
    repo = MemoryReviews()
    body = deepcopy(BODY)
    body["review"][field] = value
    with client_for(repo) as client:
        response = client.post(
            BASE + f"/{PERIOD}/loans/{LOAN}/risk-review",
            headers=HEADERS,
            json=body,
        )
    assert response.status_code == 422
    assert not repo.writes


@pytest.mark.parametrize(
    "role,permissions,status",
    [
        ("client", PERMISSIONS, "active"),
        ("management", (), "active"),
        ("management", PERMISSIONS, "inactive"),
    ],
)
def test_current_review_requires_current_management_authority(
    role, permissions, status
):
    repo = MemoryReviews()
    with client_for(
        repo, FakeAccounts(role=role, permissions=permissions, status=status)
    ) as client:
        path = BASE + f"/{PERIOD}/loans/{LOAN}/risk-review"
        assert client.get(path, headers=HEADERS).status_code == 403
        assert client.post(path, headers=HEADERS, json=BODY).status_code == 403
    assert not repo.reads and not repo.writes
