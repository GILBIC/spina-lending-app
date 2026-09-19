from importlib import import_module
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_first_loan_terms import values


def client(monkeypatch, role="management", permissions=None, device=True):
    try:
        module = import_module("gilbic_backend.first_loan_api")
    except ModuleNotFoundError:
        pytest.fail("First-loan API is not implemented", pytrace=False)
    actor = SimpleNamespace(
        user_id=uuid4(),
        registered_device_id=uuid4() if device else None,
        roles=(role,),
        permissions=permissions
        if permissions is not None
        else (
            "lending.first_loan.approve",
            "lending.first_loan.release",
            "client_onboarding.requirement.review",
        ),
    )

    def auth(**arguments):
        from fastapi import HTTPException

        if not arguments["authorization"]:
            raise HTTPException(401, "Sign in required")
        if not arguments["device_identifier"]:
            raise HTTPException(400, "Device required")
        if arguments["permission"] not in actor.permissions:
            raise HTTPException(403, "Permission required")
        return actor

    monkeypatch.setattr(module, "authenticated_device_context", auth)

    class Repository:
        def __init__(self):
            self.calls = []

        def __getattr__(self, name):
            def call(**kwargs):
                self.calls.append((name, kwargs))
                return {
                    "status": "released"
                    if name == "release"
                    else "approved_pending_release",
                    "loan_id": str(kwargs.get("loan_id", uuid4())),
                }

            return call

    repository = Repository()

    class Provisioner:
        def provision(self, **kwargs):
            assert repository.calls[-1][0] == "release"
            return {"status": "completed"}

    app = FastAPI()
    app.include_router(module.create_first_loan_router())
    app.dependency_overrides[module.first_loan_repository_dependency] = lambda: (
        repository
    )
    app.dependency_overrides[module.auth_client_dependency] = lambda: object()
    app.dependency_overrides[module.account_repository_dependency] = lambda: object()
    app.dependency_overrides[module.first_loan_post_release_dependency] = lambda: (
        Provisioner()
    )
    return TestClient(app), repository, actor, module


HEADERS = {"Authorization": "Bearer synthetic", "X-Device-Id": "synthetic-office"}


@pytest.mark.parametrize("method", ["approve", "release"])
@pytest.mark.parametrize("constraint", ["client_cif_new_credit_ready", "unrelated_check"])
def test_new_credit_guard_is_a_specific_conflict(monkeypatch, method, constraint):
    from psycopg.errors import CheckViolation

    app, repository, _, _ = client(monkeypatch)
    failure = CheckViolation(
        "private database detail",
        info={ord("n"): constraint.encode()},
    )

    def fail(**kwargs):
        repository.calls.append((method, kwargs))
        raise failure

    monkeypatch.setattr(repository, method, fail)
    if method == "approve":
        path = "/api/v1/management/first-loans/approve"
        payload = {
            "request_id": str(uuid4()),
            "application_version_id": str(uuid4()),
            "template_version": "SYNTHETIC",
            "terms": values(),
        }
    else:
        path = f"/api/v1/management/first-loans/{uuid4()}/release"
        payload = {
            "request_id": str(uuid4()),
            "packet_hash": "a" * 64,
            "authorization_id": str(uuid4()),
            "contract_evidence_reference": "office-evidence:" + str(uuid4()),
            "cash_evidence_reference": "office-evidence:" + str(uuid4()),
            "cash_amount": "990.00",
            "borrower_confirmed": True,
        }
    if constraint != "client_cif_new_credit_ready":
        with pytest.raises(CheckViolation) as caught:
            app.post(path, headers=HEADERS, json=payload)
        assert caught.value is failure
    else:
        response = app.post(path, headers=HEADERS, json=payload)
        assert response.status_code == 409
        assert response.headers["cache-control"] == "no-store"
        assert "Refresh" in response.json()["detail"]
        assert "private database detail" not in response.text
        assert "credentials" not in response.json()
    assert len(repository.calls) == 1


def test_management_approval_passes_exact_snapshot_identity_and_terms(monkeypatch):
    app, repository, actor, _ = client(monkeypatch)
    payload = {
        "request_id": str(uuid4()),
        "application_version_id": str(uuid4()),
        "template_version": "SYNTHETIC",
        "terms": values(),
    }
    response = app.post(
        "/api/v1/management/first-loans/approve", headers=HEADERS, json=payload
    )
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    name, args = repository.calls[0]
    assert (
        name == "approve"
        and args["actor_user_id"] == actor.user_id
        and args["registered_device_id"] == actor.registered_device_id
    )
    assert args["terms"]["principal"] == "1000.00"


@pytest.mark.parametrize("role", ["employee", "collector", "client"])
def test_only_management_can_approve_even_with_permission(monkeypatch, role):
    app, repository, _, _ = client(monkeypatch, role=role)
    response = app.post(
        "/api/v1/management/first-loans/approve",
        headers=HEADERS,
        json={
            "request_id": str(uuid4()),
            "application_version_id": str(uuid4()),
            "template_version": "SYNTHETIC",
            "terms": values(),
        },
    )
    assert (
        response.status_code == 403 and response.headers["cache-control"] == "no-store"
    )
    assert repository.calls == []


@pytest.mark.parametrize("missing", ["Authorization", "X-Device-Id"])
def test_authentication_and_device_remain_required(monkeypatch, missing):
    app, repository, _, _ = client(monkeypatch)
    response = app.get(
        "/api/v1/management/first-loans/context",
        headers={k: v for k, v in HEADERS.items() if k != missing},
    )
    assert response.status_code in (400, 401)
    assert repository.calls == []


def test_nonpersisted_device_fails_closed(monkeypatch):
    app, repository, _, _ = client(monkeypatch, device=False)
    response = app.get("/api/v1/management/first-loans/context", headers=HEADERS)
    assert response.status_code == 403 and repository.calls == []


def test_release_provisions_after_financial_commit_and_never_accepts_browser_terms(
    monkeypatch,
):
    app, repository, actor, _ = client(monkeypatch, role="employee")
    payload = {
        "request_id": str(uuid4()),
        "packet_hash": "a" * 64,
        "authorization_id": str(uuid4()),
        "contract_evidence_reference": "office-evidence:" + str(uuid4()),
        "cash_evidence_reference": "office-evidence:" + str(uuid4()),
        "cash_amount": "990.00",
        "borrower_confirmed": True,
    }
    response = app.post(
        f"/api/v1/management/first-loans/{uuid4()}/release",
        headers=HEADERS,
        json=payload,
    )
    assert (
        response.status_code == 200
        and response.json()["credentials"]["status"] == "completed"
    )
    assert repository.calls[0][1]["actor_user_id"] == actor.user_id
    payload["principal"] = "1.00"
    response = app.post(
        f"/api/v1/management/first-loans/{uuid4()}/release",
        headers=HEADERS,
        json=payload,
    )
    assert response.status_code == 422 and len(repository.calls) == 1


@pytest.mark.parametrize("confirmation", [None, False, "true", 1])
def test_contract_evidence_requires_explicit_witnessed_signature(
    monkeypatch, confirmation
):
    app, repository, _, _ = client(monkeypatch, role="employee")
    payload = {
        "request_id": str(uuid4()),
        "packet_hash": "a" * 64,
        "purpose": "borrower_contract_signed",
        "media_type": "application/pdf",
        "content_base64": "JVBERi0xLjQ=",
    }
    if confirmation is not None:
        payload["witnessed_wet_signature"] = confirmation
    response = app.post(
        f"/api/v1/management/first-loans/{uuid4()}/evidence",
        headers=HEADERS,
        json=payload,
    )
    assert response.status_code == 422
    assert repository.calls == []


def test_contract_evidence_passes_explicit_witnessed_signature(monkeypatch):
    app, repository, _, _ = client(monkeypatch, role="employee")
    payload = {
        "request_id": str(uuid4()),
        "packet_hash": "a" * 64,
        "purpose": "borrower_contract_signed",
        "media_type": "application/pdf",
        "content_base64": "JVBERi0xLjQ=",
        "witnessed_wet_signature": True,
    }
    response = app.post(
        f"/api/v1/management/first-loans/{uuid4()}/evidence",
        headers=HEADERS,
        json=payload,
    )
    assert response.status_code == 201
    assert repository.calls[0][1]["witnessed_wet_signature"] is True
