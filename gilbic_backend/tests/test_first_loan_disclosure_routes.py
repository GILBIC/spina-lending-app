"""Protected HTTP boundary; persisted authority remains covered by PostgreSQL."""

from copy import deepcopy
from uuid import UUID, uuid4

import pytest
import test_first_loan_api as api_proof
from first_loan_disclosure_fixtures import SUPPORT, review_values

PREFIX = "/api/v1/management/first-loans"
CALCULATION = "00000000-0000-4000-8000-000000000007"
APPLICATION = "00000000-0000-4000-8000-000000000003"


def client(monkeypatch, **options):
    app, repository, actor, module = api_proof.client(monkeypatch, **options)
    dependency = getattr(module, "first_loan_disclosure_repository_dependency", None)
    if dependency is not None:
        app.app.dependency_overrides[dependency] = lambda: repository
    return app, repository, actor, module


def context_values():
    values = review_values()
    return {
        key: values[key]
        for key in (
            "application_version_id",
            "cif_version_id",
            "terms",
            "dst_rule_id",
            "grt_rule_id",
        )
    }


OPERATIONS = (
    ("POST", "/disclosure-context", "context", context_values()),
    ("POST", "/disclosure-calculations", "record", review_values()),
    ("GET", f"/disclosure-calculations/by-request/{uuid4()}", "by_request", None),
    (
        "GET",
        f"/disclosure-calculations/{CALCULATION}?application_version_id={APPLICATION}",
        "get",
        None,
    ),
    (
        "GET",
        f"/disclosure-calculations/{CALCULATION}/support?application_version_id={APPLICATION}",
        "support",
        None,
    ),
)


@pytest.mark.parametrize("method,path,owner,payload", OPERATIONS)
def test_exact_authorized_route_uses_persisted_actor_once(
    monkeypatch, method, path, owner, payload
):
    app, repository, actor, _ = client(monkeypatch)
    saved = {
        "id": CALCULATION,
        "financial_snapshot": {"components": {"principal": "1000.00"}},
        "approval_ready": False,
        "blockers": ["source_context_changed"],
    }

    def call(**arguments):
        repository.calls.append((owner, arguments))
        return (
            ({"media_type": "application/pdf"}, SUPPORT)
            if owner == "support"
            else deepcopy(saved)
        )

    monkeypatch.setattr(repository, owner, call)
    response = app.request(
        method, PREFIX + path, headers=api_proof.HEADERS, json=payload
    )
    assert response.status_code == (201 if owner == "record" else 200)
    assert response.headers["cache-control"] == "no-store"
    assert len(repository.calls) == 1
    name, args = repository.calls[0]
    assert name == owner
    assert args["actor_user_id"] == actor.user_id
    assert args["registered_device_id"] == actor.registered_device_id
    if owner == "record":
        assert (
            args["request"].model_dump(mode="json")["components"]["principal"]
            == "1000.00"
        )
        assert args["request"].support_base64 == payload["support_base64"]
    elif owner == "context":
        assert args["application_version_id"] == UUID(APPLICATION)
        assert args["terms"]["principal"] == "1000.00"
    elif owner in {"get", "support"}:
        assert args["calculation_id"] == UUID(CALCULATION)
        assert args["application_version_id"] == UUID(APPLICATION)
    else:
        assert args["request_id"] == UUID(path.rsplit("/", 1)[1])
    if owner == "support":
        assert response.content == SUPPORT
        assert response.headers["content-type"] == "application/pdf"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert "attachment" in response.headers["content-disposition"]
        assert "location" not in response.headers
    else:
        assert response.json() == saved


@pytest.mark.parametrize("method,path,owner,payload", OPERATIONS)
@pytest.mark.parametrize(
    "restriction",
    ["unsigned", "employee", "collector", "client", "permission", "device", "revoked"],
)
def test_disclosure_route_denies_invalid_authority_before_repository(
    monkeypatch, method, path, owner, payload, restriction
):
    options = {}
    headers = api_proof.HEADERS
    if restriction in {"employee", "collector", "client"}:
        options["role"] = restriction
    elif restriction == "permission":
        options["permissions"] = ()
    elif restriction == "device":
        options["device"] = False
    elif restriction == "unsigned":
        headers = {}
    app, repository, _, module = client(monkeypatch, **options)
    if restriction == "revoked":
        from fastapi import HTTPException

        def denied(**arguments):
            raise HTTPException(403, "Device revoked")

        monkeypatch.setattr(module, "authenticated_device_context", denied)
    response = app.request(method, PREFIX + path, headers=headers, json=payload)
    if restriction == "employee" and owner == "get":
        assert response.status_code == 200
        assert len(repository.calls) == 1
    else:
        assert response.status_code == (401 if restriction == "unsigned" else 403)
        assert repository.calls == []
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "field,value",
    [
        ("support_base64", "PRIVATE invalid base64!"),
        ("reviewed_by_user_id", "PRIVATE forged actor"),
        ("approval_ready", True),
        ("expected_context_digest", "PRIVATE invalid digest"),
        ("review_rationale", ""),
        ("components", {"principal": "PRIVATE source value"}),
    ],
)
def test_invalid_review_does_not_echo_private_request(monkeypatch, field, value):
    app, repository, _, _ = client(monkeypatch)
    payload = review_values(**{field: value})
    response = app.post(
        PREFIX + "/disclosure-calculations", headers=api_proof.HEADERS, json=payload
    )
    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"
    assert "PRIVATE" not in response.text
    assert payload["support_base64"] not in response.text
    assert (
        payload["review_rationale"] == ""
        or payload["review_rationale"] not in response.text
    )
    assert repository.calls == []


def test_over_limit_review_support_has_small_private_error(monkeypatch):
    from gilbic_backend.first_loan_disclosure import MAX_SUPPORT_BASE64

    app, repository, _, _ = client(monkeypatch)
    response = app.post(
        PREFIX + "/disclosure-calculations",
        headers=api_proof.HEADERS,
        json=review_values(support_base64="A" * (MAX_SUPPORT_BASE64 + 4)),
    )
    assert response.status_code == 422
    assert len(response.content) < 1000
    assert response.headers["cache-control"] == "no-store"
    assert repository.calls == []


@pytest.mark.parametrize("suffix", ["", "/support"])
def test_summary_and_support_require_application_coordinate(monkeypatch, suffix):
    app, repository, _, _ = client(monkeypatch)
    response = app.get(
        PREFIX + f"/disclosure-calculations/{CALCULATION}{suffix}",
        headers=api_proof.HEADERS,
    )
    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"
    assert repository.calls == []


@pytest.mark.parametrize("method,path,owner,payload", OPERATIONS)
def test_foreign_or_stale_source_returns_safe_conflict_once(
    monkeypatch, method, path, owner, payload
):
    app, repository, _, module = client(monkeypatch)

    def denied(**arguments):
        repository.calls.append((owner, arguments))
        raise module.FirstLoanConflict("The disclosure record is unavailable.")

    monkeypatch.setattr(repository, owner, denied)
    response = app.request(
        method, PREFIX + path, headers=api_proof.HEADERS, json=payload
    )
    assert response.status_code == 409
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"detail": "The disclosure record is unavailable."}
    assert len(repository.calls) == 1
