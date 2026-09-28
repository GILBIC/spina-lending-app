"""Task 5 approval transport; existing PostgreSQL tests own source acceptance.

Reuse the existing injected HTTP fixture. These are API-boundary tests, not
proof that a guessed calculation ID is valid or that a financial action ran.
"""

from copy import deepcopy
from uuid import UUID, uuid4

import pytest
import test_first_loan_api as api_proof
from test_first_loan_terms import values

PREFIX = "/api/v1/management/first-loans"


def _approval():
    return {
        "request_id": str(uuid4()),
        "application_version_id": str(uuid4()),
        "template_version": "SYNTHETIC",
        "terms": values(),
        "disclosure_calculation_id": str(uuid4()),
        "expected_disclosure_digest": "a" * 64,
    }


def test_approval_forwards_exact_saved_source_and_terms(monkeypatch):
    app, repository, actor, module = api_proof.client(monkeypatch)
    payload = _approval()
    before = deepcopy(payload)
    response = app.post(PREFIX + "/approve", headers=api_proof.HEADERS, json=payload)
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert payload == before
    assert len(repository.calls) == 1
    method, arguments = repository.calls[0]
    assert method == "approve"
    assert arguments == {
        "actor_user_id": actor.user_id,
        "registered_device_id": actor.registered_device_id,
        "request_id": UUID(payload["request_id"]),
        "application_version_id": UUID(payload["application_version_id"]),
        "template_version": payload["template_version"],
        "terms": module.FirstLoanTerms.model_validate(payload["terms"]).model_dump(
            mode="json"
        ),
        "disclosure_calculation_id": UUID(payload["disclosure_calculation_id"]),
        "expected_disclosure_digest": payload["expected_disclosure_digest"],
    }
    assert arguments["terms"]["principal"] == "1000.00"
    assert arguments["terms"]["interest_rate_percent"] == "20.0000"


@pytest.mark.parametrize(
    "field,value",
    (
        ("disclosure_calculation_id", "not-a-uuid"),
        ("disclosure_calculation_id", True),
        ("disclosure_calculation_id", 1),
        ("disclosure_calculation_id", None),
        ("expected_disclosure_digest", None),
        ("expected_disclosure_digest", ""),
        ("expected_disclosure_digest", "a" * 63),
        ("expected_disclosure_digest", "a" * 65),
        ("expected_disclosure_digest", "A" * 64),
        ("expected_disclosure_digest", "z" * 64),
        ("expected_disclosure_digest", True),
        ("expected_disclosure_digest", 1),
    ),
)
def test_invalid_or_partial_source_pair_stops_before_repository(
    monkeypatch, field, value
):
    app, repository, _, _ = api_proof.client(monkeypatch)
    payload = _approval()
    payload[field] = value
    response = app.post(PREFIX + "/approve", headers=api_proof.HEADERS, json=payload)
    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"
    assert repository.calls == []


@pytest.mark.parametrize(
    "missing", ("disclosure_calculation_id", "expected_disclosure_digest")
)
def test_omitting_only_one_source_field_cannot_downgrade_the_request(
    monkeypatch, missing
):
    app, repository, _, _ = api_proof.client(monkeypatch)
    payload = _approval()
    del payload[missing]
    response = app.post(PREFIX + "/approve", headers=api_proof.HEADERS, json=payload)
    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"
    assert repository.calls == []


@pytest.mark.parametrize("historical", (False, True))
def test_absent_pair_is_adjudicated_once_by_existing_repository(
    monkeypatch, historical
):
    app, repository, _, module = api_proof.client(monkeypatch)
    payload = _approval()
    del payload["disclosure_calculation_id"]
    del payload["expected_disclosure_digest"]
    retained = {"status": "released", "packet": {"schema_version": 1}}

    def approve(**arguments):
        repository.calls.append(("approve", arguments))
        # Boundary fixture only. Real new-approval denial and immutable replay
        # are independently exercised by the retained PostgreSQL suites.
        assert arguments["disclosure_calculation_id"] is None
        assert arguments["expected_disclosure_digest"] is None
        if not historical:
            raise module.FirstLoanConflict("A saved disclosure source is required.")
        return deepcopy(retained)

    monkeypatch.setattr(repository, "approve", approve)
    response = app.post(PREFIX + "/approve", headers=api_proof.HEADERS, json=payload)
    assert response.status_code == (201 if historical else 409)
    assert response.headers["cache-control"] == "no-store"
    assert len(repository.calls) == 1
    assert repository.calls[0][1]["request_id"] == UUID(payload["request_id"])
    if historical:
        assert response.json() == retained
    else:
        assert response.json() == {"detail": "A saved disclosure source is required."}


@pytest.mark.parametrize("role", ("management", "employee"))
def test_context_advertises_source_requirement_without_mutating_repository_result(
    monkeypatch, role
):
    app, repository, actor, _ = api_proof.client(monkeypatch, role=role)
    retained = {"server_business_date": "2026-09-27", "templates": [], "products": []}
    before = deepcopy(retained)

    def context(**arguments):
        repository.calls.append(("context", arguments))
        return retained

    monkeypatch.setattr(repository, "context", context)
    response = app.get(PREFIX + "/context", headers=api_proof.HEADERS)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {**before, "disclosure_source_required": True}
    assert retained == before
    assert repository.calls == [
        (
            "context",
            {
                "actor_user_id": actor.user_id,
                "registered_device_id": actor.registered_device_id,
            },
        )
    ]


@pytest.mark.parametrize("role", ("employee", "collector", "client"))
def test_valid_source_pair_never_grants_management_authority(monkeypatch, role):
    app, repository, _, _ = api_proof.client(monkeypatch, role=role)
    response = app.post(
        PREFIX + "/approve", headers=api_proof.HEADERS, json=_approval()
    )
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
    assert repository.calls == []


def test_source_conflict_never_retries_without_the_pair(monkeypatch):
    app, repository, _, module = api_proof.client(monkeypatch)
    payload = _approval()

    def approve(**arguments):
        repository.calls.append(("approve", arguments))
        raise module.FirstLoanConflict("Reload the current disclosure context.")

    monkeypatch.setattr(repository, "approve", approve)
    response = app.post(PREFIX + "/approve", headers=api_proof.HEADERS, json=payload)
    assert response.status_code == 409
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"detail": "Reload the current disclosure context."}
    assert len(repository.calls) == 1
    assert repository.calls[0][1]["disclosure_calculation_id"] == UUID(
        payload["disclosure_calculation_id"]
    )
    assert repository.calls[0][1]["expected_disclosure_digest"] == "a" * 64
