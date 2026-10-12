"""Historical inputs are explicit; retained calculations and actors are server-owned."""

from copy import deepcopy
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

BOOK, PERIOD, LOAN, PREPARATION, POSTING, EVIDENCE = [str(uuid4()) for _ in range(6)]
BASE = "/api/v1/management/financial-accounting/period-elapsed-assessments"
PATH = BASE + f"/{PERIOD}/loans/{LOAN}"
PERMISSIONS = (
    "accounting.view",
    "accounting.period.close.prepare",
    "accounting.period.close.post",
)
BODY = {
    "expected_book_id": BOOK,
    "source_digest": "a" * 64,
    "review_rationale": "Reviewed historical source identity and explicit economic forecasts.",
    "risk_review": {
        "as_of_date": "2026-09-30",
        "stage_label": "stage_1_12_month",
        "default_label": False,
        "write_off_label": "none",
        "recovery_label": "none",
        "primary_evidence_basis": "contractual_dpd",
        "evidence_reference": "signed:contract",
        "review_note": "Reviewed actual contractual conditions as of the historical cutoff.",
    },
    "scenarios": [
        {
            "scenario_key": key,
            "probability": probability,
            "evidence_reference": "published:economic-source",
            "management_rationale": "The dated retained source supports this explicit receipt scenario.",
            "forward_evidence_ids": [EVIDENCE],
            "expected_cash_flows": [{"cash_date": "2026-10-01", "amount": amount}],
        }
        for key, probability, amount in (
            ("base", "0.7", "9999999999999999.99"),
            ("downside", "0.3", "40.00"),
        )
    ],
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
        return {
            "preparation_id": PREPARATION,
            "confirmation_digest": "b" * 64,
            "calculated_at": "2026-10-05T10:00:00+00:00",
        }

    def confirm(self, **values):
        self.writes.append(values)
        return POSTING


def client_for(repo, accounts=None):
    try:
        api = import_module("gilbic_backend.elapsed_period_assessment_api")
    except ModuleNotFoundError:
        pytest.fail("Historical elapsed assessment API is not implemented")
    app = FastAPI()
    app.include_router(api.create_elapsed_period_assessment_router())
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuth()
    app.dependency_overrides[account_repository_dependency] = lambda: (
        accounts or FakeAccounts(permissions=PERMISSIONS)
    )
    app.dependency_overrides[api.elapsed_period_assessment_repository_dependency] = (
        lambda: repo
    )
    return TestClient(app)


@pytest.mark.parametrize("base", [BASE, BASE.replace("/api/v1/", "/api/mobile/v1/")])
def test_historical_review_returns_confirmation_identity_and_preserves_exact_inputs(
    base,
):
    repo = MemoryAssessments()
    with client_for(repo) as client:
        path = base + f"/{PERIOD}/loans/{LOAN}"
        assert client.get(path, headers=HEADERS).status_code == 200
        response = client.post(path + "/prepare", headers=HEADERS, json=BODY)
    assert response.status_code == 200
    assert response.json()["data"]["confirmation_digest"] == "b" * 64
    values = repo.writes[0]
    assert values["actor_user_id"] == ACTOR and str(values["loan_id"]) == LOAN
    assert (
        values["scenarios"][0]["expected_cash_flows"][0]["amount"]
        == "9999999999999999.99"
    )
    assert values["risk_review"]["as_of_date"] == "2026-09-30"


@pytest.mark.parametrize(
    "field,value",
    [
        ("actor_user_id", BOOK),
        ("calculated_at", "2026-09-30"),
        ("measurement_snapshot", {}),
        ("source_digest", "invalid"),
    ],
)
def test_client_cannot_supply_retained_authority(field, value):
    repo = MemoryAssessments()
    with client_for(repo) as client:
        response = client.post(
            PATH + "/prepare", headers=HEADERS, json=BODY | {field: value}
        )
    assert response.status_code == 422 and repo.writes == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("probability", 0.7),
        ("probability", "0.7000000000001"),
        ("amount", 50.1),
        ("amount", "50.001"),
    ],
)
def test_amount_and_probability_inputs_never_pass_through_binary_float(field, value):
    repo = MemoryAssessments()
    body = deepcopy(BODY)
    if field == "probability":
        body["scenarios"][0][field] = value
    else:
        body["scenarios"][0]["expected_cash_flows"][0][field] = value
    with client_for(repo) as client:
        response = client.post(PATH + "/prepare", headers=HEADERS, json=body)
    assert response.status_code == 422 and repo.writes == []


def test_confirmation_requires_explicit_boolean_and_prepared_digest():
    repo = MemoryAssessments()
    body = {"expected_book_id": BOOK, "confirmation_digest": "b" * 64, "confirm": True}
    with client_for(repo) as client:
        path = BASE + f"/preparations/{PREPARATION}/confirm"
        assert (
            client.post(
                path, headers=HEADERS, json=body | {"confirm": "true"}
            ).status_code
            == 422
        )
        assert (
            client.post(
                path, headers=HEADERS, json=body | {"confirm": False}
            ).status_code
            == 409
        )
        response = client.post(path, headers=HEADERS, json=body)
    assert response.status_code == 200
    assert response.json()["data"]["posting_id"] == POSTING
    assert len(repo.writes) == 1 and repo.writes[0]["actor_user_id"] == ACTOR


@pytest.mark.parametrize(
    "role,permissions,status",
    [
        ("client", PERMISSIONS, "active"),
        ("management", (), "active"),
        ("management", PERMISSIONS, "inactive"),
    ],
)
def test_historical_inputs_require_current_management_authority(
    role, permissions, status
):
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
