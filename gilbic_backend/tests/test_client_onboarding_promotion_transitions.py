"""Actual repository transitions against a synthetic SQL storage boundary."""

import re
from copy import deepcopy
from uuid import UUID

import psycopg
import pytest
from gilbic_backend.client_onboarding_api import client_onboarding_repository_dependency
from test_client_onboarding_review_api import (
    APPLICANT_ID,
    _client_for,
    _document_body,
    _headers,
)

from gilbic_backend import client_onboarding_repository as module

ACTOR = UUID(int=40)
CLIENT = UUID(int=41)


class OnboardingStorage:
    """Model row persistence and unique client codes, without executing PostgreSQL."""

    def __init__(self, *, promoted=True, status="eligible_for_cif"):
        self.applicant = {
            "application_reference": "APP-SYNTHETIC-42",
            "status": status,
            "full_name": "Synthetic Applicant",
            "phone_number": "09000000000",
            "national_id_status": "passed",
            "tin_id_status": "passed",
            "meralco_bill_status": "passed",
            "collector_visit_status": "passed",
            "promoted_client_id": CLIENT if promoted else None,
        }
        self.clients = {"CLIENT-SYNTHETIC-42": CLIENT} if promoted else {}
        self.result = None
        self.audit_events = []
        self.insert_attempts = 0

    def __enter__(self):
        self.before = deepcopy((self.applicant, self.clients, self.audit_events))
        return self

    def __exit__(self, exc_type, *args):
        if exc_type:
            self.applicant, self.clients, self.audit_events = self.before

    def cursor(self):
        return Cursor(self)

    def project(self, fields):
        return tuple(self.applicant[field.strip()] for field in fields.split(","))


class Cursor:
    def __init__(self, storage):
        self.storage = storage

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, query, params=()):
        query = " ".join(query.split())
        storage = self.storage
        storage.result = None
        if query.startswith("select "):
            assert "from lending.client_onboarding_applicants" in query
            storage.result = storage.project(query.split(" from ")[0][7:])
        elif query.startswith("update lending.client_onboarding_applicants"):
            assignments = query.split(" set ", 1)[1].split(" where ", 1)[0]
            values = iter(params[:-1])
            for name, expression in re.findall(
                r"(\w+)\s*=\s*(%s|'[^']*'|now\(\))", assignments
            ):
                if expression == "%s":
                    storage.applicant[name] = next(values)
                elif expression.startswith("'"):
                    storage.applicant[name] = expression[1:-1]
            if " returning " in query:
                storage.result = storage.project(query.split(" returning ", 1)[1])
        elif query.startswith("insert into lending.clients"):
            storage.insert_attempts += 1
            if params[0] in storage.clients:
                raise psycopg.errors.UniqueViolation("client_code must be unique")
            storage.clients[params[0]] = CLIENT
            storage.result = (CLIENT,)
        elif query.startswith("insert into core.audit_logs"):
            storage.audit_events.append(query)
        else:
            raise AssertionError(f"Unexpected storage operation: {query}")
        return self

    def fetchone(self):
        return self.storage.result


def repository(monkeypatch, **kwargs):
    storage = OnboardingStorage(**kwargs)
    monkeypatch.setattr(module, "open_connection", lambda: storage)
    return module.PostgresClientOnboardingRepository(), storage


def review(repo, **changes):
    return repo.review_document_requirements(
        actor_user_id=ACTOR,
        applicant_id=APPLICANT_ID,
        **{**_document_body(), **changes},
    )


def test_unchanged_promoted_document_review_preserves_identity_and_cif_eligibility(
    monkeypatch,
):
    repo, storage = repository(monkeypatch)
    before = deepcopy(storage.applicant)
    result = review(repo)
    assert result.status == "eligible_for_cif"
    assert result.promoted_client_id == CLIENT
    again = repo.approve_normal_eligibility(
        actor_user_id=ACTOR, applicant_id=APPLICANT_ID
    )
    assert again.promoted_client_id == CLIENT
    assert storage.applicant == before
    assert storage.clients == {"CLIENT-SYNTHETIC-42": CLIENT}
    assert storage.insert_attempts == 0
    assert storage.audit_events == []


@pytest.mark.parametrize(
    "field", ["national_id_status", "tin_id_status", "meralco_bill_status"]
)
def test_changed_promoted_document_review_is_a_conflict_without_state_changes(
    monkeypatch, field
):
    repo, storage = repository(monkeypatch)
    before = deepcopy(storage.applicant)
    with pytest.raises(ValueError, match="[Pp]romot|[Cc]lient"):
        review(repo, **{field: "failed"})
    assert storage.applicant == before
    assert storage.clients == {"CLIENT-SYNTHETIC-42": CLIENT}
    assert storage.audit_events == []


@pytest.mark.parametrize("bypass", [False, True])
def test_legacy_demoted_promoted_applicant_cannot_create_another_client(
    monkeypatch, bypass
):
    repo, storage = repository(monkeypatch, status="under_verification")
    if bypass:
        storage.applicant["national_id_status"] = "failed"
    before = deepcopy(storage.applicant)
    with pytest.raises(ValueError, match="[Pp]romot|[Cc]lient"):
        if bypass:
            repo.bypass_and_approve_eligibility(
                actor_user_id=ACTOR,
                applicant_id=APPLICANT_ID,
                bypassed_requirements=["national_id"],
                reason="Reviewed exception",
            )
        else:
            repo.approve_normal_eligibility(
                actor_user_id=ACTOR, applicant_id=APPLICANT_ID
            )
    assert storage.applicant == before
    assert storage.insert_attempts == 0
    assert storage.clients == {"CLIENT-SYNTHETIC-42": CLIENT}


@pytest.mark.parametrize(
    "failed,status", [(False, "under_verification"), (True, "requirements_rejected")]
)
def test_unpromoted_document_review_still_records_requirements(
    monkeypatch, failed, status
):
    repo, storage = repository(
        monkeypatch, promoted=False, status="requirements_incomplete"
    )
    result = review(repo, national_id_status="failed" if failed else "passed")
    assert result.status == status
    assert storage.applicant["national_id_status"] == ("failed" if failed else "passed")
    assert len(storage.audit_events) == 1
    assert storage.clients == {}


def test_fresh_eligible_applicant_still_creates_exactly_one_identity(monkeypatch):
    repo, storage = repository(monkeypatch, promoted=False, status="under_verification")
    first = repo.approve_normal_eligibility(
        actor_user_id=ACTOR, applicant_id=APPLICANT_ID
    )
    second = repo.approve_normal_eligibility(
        actor_user_id=ACTOR, applicant_id=APPLICANT_ID
    )
    assert first.promoted_client_id == second.promoted_client_id == CLIENT
    assert storage.applicant["status"] == "eligible_for_cif"
    assert storage.insert_attempts == 1
    assert len(storage.clients) == 1


def test_promoted_document_change_returns_actionable_http_conflict(monkeypatch):
    repo, storage = repository(monkeypatch)
    client, _ = _client_for(
        role="management", permissions=("client_onboarding.requirement.review",)
    )
    client.app.dependency_overrides[client_onboarding_repository_dependency] = lambda: (
        repo
    )
    with client:
        response = client.patch(
            f"/api/v1/management/onboarding/applicants/{APPLICANT_ID}/document-requirements",
            headers=_headers(),
            json={**_document_body(), "national_id_status": "failed"},
        )
    assert response.status_code == 409
    assert "promot" in response.json()["detail"].lower()
    assert storage.applicant["status"] == "eligible_for_cif"


@pytest.mark.parametrize("bypass", [False, True])
def test_legacy_promoted_state_conflict_is_reported_by_eligibility_api(
    monkeypatch, bypass
):
    repo, storage = repository(monkeypatch, status="under_verification")
    permission = (
        "client_onboarding.bypass" if bypass else "client_onboarding.requirement.review"
    )
    client, _ = _client_for(role="management", permissions=(permission,))
    client.app.dependency_overrides[client_onboarding_repository_dependency] = lambda: (
        repo
    )
    suffix = "/bypass" if bypass else ""
    body = (
        {"bypassed_requirements": ["national_id"], "reason": "Reviewed exception"}
        if bypass
        else None
    )
    with client:
        response = client.post(
            f"/api/v1/management/onboarding/applicants/{APPLICANT_ID}/eligibility{suffix}",
            headers=_headers(),
            json=body,
        )
    assert response.status_code == 409
    assert "promot" in response.json()["detail"].lower()
    assert storage.insert_attempts == 0
