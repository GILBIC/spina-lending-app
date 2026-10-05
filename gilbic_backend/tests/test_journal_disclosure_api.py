from importlib.util import find_spec
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from gilbic_backend.auth_api import (
    account_repository_dependency,
    auth_client_dependency,
)
from test_financial_statements import MANAGEMENT_USER_ID, FakeAuthClient, headers
from test_reporting_evidence_api import Accounts


class Repository:
    def __init__(self):
        self.calls = []

    def load_disclosures(self, **kwargs):
        self.calls.append(kwargs)
        return {"status": "disclosure_review_required"}

    def retain_disclosure_policy(self, **kwargs):
        self.calls.append(kwargs)
        return kwargs["request_id"]

    retain_disclosure = retain_disclosure_policy


def client(**kwargs):
    assert find_spec("gilbic_backend.journal_disclosure_api"), (
        "Disclosure API is not implemented"
    )
    from gilbic_backend.journal_disclosure_api import (
        create_journal_disclosure_router,
        journal_disclosure_repository_dependency,
    )

    app = FastAPI()
    app.include_router(create_journal_disclosure_router())
    repo = Repository()
    app.dependency_overrides[auth_client_dependency] = FakeAuthClient
    app.dependency_overrides[account_repository_dependency] = lambda: Accounts(**kwargs)
    app.dependency_overrides[journal_disclosure_repository_dependency] = lambda: repo
    return TestClient(app), repo


def body():
    return {
        "request_id": str(uuid4()),
        "book_id": str(uuid4()),
        "disclosure_policy_id": str(uuid4()),
        "journal_entry_id": str(uuid4()),
        "expected_version": 0,
        "source_digest": "a" * 64,
        "components": [
            {
                "debit_line_id": str(uuid4()),
                "credit_line_id": str(uuid4()),
                "amount": "600.00",
                "classification": "noncash_investing_financing",
                "evidence_reference": "test:contract",
                "evidence_digest": "b" * 64,
            }
        ],
        "reason": "Reviewed mixed funding.",
        "evidence_reference": "test:mixed",
        "evidence_digest": "c" * 64,
        "reviewed": True,
    }


@pytest.mark.parametrize("prefix", ["/api/v1", "/api/mobile/v1"])
def test_read_and_retain_use_current_server_actor(prefix):
    api, repo = client()
    root = prefix + "/management/financial-accounting/statements"
    response = api.get(
        root + "/disclosures", params={"period_id": str(uuid4())}, headers=headers()
    )
    assert response.status_code == 200
    request = body()
    response = api.post(root + "/disclosure-reviews", json=request, headers=headers())
    assert response.status_code == 200
    assert response.json()["data"]["review_id"] == request["request_id"]
    assert repo.calls[-1]["payload"]["components"][0]["amount"] == "600.00"
    assert all(call["actor_user_id"] == MANAGEMENT_USER_ID for call in repo.calls)


@pytest.mark.parametrize(
    "change",
    [
        {"expected_version": True},
        {"actor_user_id": str(uuid4())},
        {"source_digest": "invalid"},
        {"components": []},
    ],
)
def test_bad_coordinates_do_not_reach_retention(change):
    api, repo = client()
    result = api.post(
        "/api/v1/management/financial-accounting/statements/disclosure-reviews",
        json=body() | change,
        headers=headers(),
    )
    assert result.status_code == 422
    assert not repo.calls


@pytest.mark.parametrize(
    ("settings", "reviewed", "status"),
    [
        ({"can_manage": False}, True, 403),
        ({"role": "collector"}, True, 403),
        ({}, False, 409),
    ],
)
def test_current_permission_and_explicit_review_required(settings, reviewed, status):
    api, repo = client(**settings)
    result = api.post(
        "/api/v1/management/financial-accounting/statements/disclosure-reviews",
        json=body() | {"reviewed": reviewed},
        headers=headers(),
    )
    assert result.status_code == status
    assert not repo.calls


def test_financing_policy_allows_explicit_no_financing_liabilities():
    api, repo = client()
    request = {
        "request_id": str(uuid4()),
        "book_id": str(uuid4()),
        "reporting_policy_id": str(uuid4()),
        "expected_version": 0,
        "financing_account_codes": [],
        "evidence_reference": "test:policy",
        "evidence_digest": "a" * 64,
        "reviewed": True,
    }
    result = api.post(
        "/api/v1/management/financial-accounting/statements/disclosure-policy",
        json=request,
        headers=headers(),
    )
    assert result.status_code == 200
    assert repo.calls[-1]["payload"]["financing_account_codes"] == []
