from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gilbic_backend import first_loan_document_api as api
from gilbic_backend.first_loan_repository import FirstLoanAccessDenied


def client(monkeypatch, *, role="management", permission=True, device=True):
    calls = []
    document = {"id": str(uuid4()), "content_sha256": "b" * 64}
    record = {
        "packet_hash": "a" * 64,
        "document": None,
        "pricing_snapshot": {"kind": "synthetic"},
    }

    class Repository:
        def get(self, **kwargs):
            calls.append(("get", kwargs))
            return record

        def packet_document(self, **kwargs):
            calls.append(("download", kwargs))
            return document, b"%PDF-1.4\nsynthetic"

        def register_packet_document(self, **kwargs):
            calls.append(("register", kwargs))
            record["document"] = document
            return document

    actor = SimpleNamespace(
        user_id=uuid4(),
        registered_device_id=uuid4() if device else None,
        roles=(role,),
        permissions=(api.APPROVE_PERMISSION,) if permission else (),
    )
    repository = Repository()
    app = FastAPI()
    app.include_router(api.create_first_loan_document_router())
    app.dependency_overrides[api._actor] = lambda: actor
    app.dependency_overrides[api.first_loan_repository_dependency] = lambda: repository

    def render(value):
        calls.append(("render", value["packet_hash"]))
        return b"%PDF-1.4\nsynthetic"

    monkeypatch.setattr(api, "render_packet", render)
    return TestClient(app), repository, calls, record, actor


@pytest.mark.parametrize(
    "arguments",
    [
        dict(role="employee"),
        dict(role="collector"),
        dict(role="client"),
        dict(permission=False),
        dict(device=False),
    ],
)
def test_only_authorized_management_with_device_can_issue(monkeypatch, arguments):
    app, _, calls, _, _ = client(monkeypatch, **arguments)
    result = app.post(
        f"/api/v1/management/first-loans/{uuid4()}/documents",
        json={"packet_hash": "a" * 64},
    )
    assert result.status_code == 403
    assert result.headers["cache-control"] == "no-store"
    assert calls == []


def test_stale_packet_and_browser_supplied_document_are_rejected_without_rendering(
    monkeypatch,
):
    app, _, calls, _, _ = client(monkeypatch)
    url = f"/api/v1/management/first-loans/{uuid4()}/documents"
    assert app.post(url, json={"packet_hash": "c" * 64}).status_code == 409
    assert [name for name, _ in calls] == ["get"]
    calls.clear()
    response = app.post(url, json={"packet_hash": "a" * 64, "content": "untrusted"})
    assert (
        response.status_code == 422 and response.headers["cache-control"] == "no-store"
    )
    assert calls == []


def test_uncertain_issuance_retry_loads_stored_document_without_regeneration(
    monkeypatch,
):
    app, _, calls, _, actor = client(monkeypatch)
    loan_id = uuid4()
    url = f"/api/v1/management/first-loans/{loan_id}/documents"
    first = app.post(url, json={"packet_hash": "a" * 64})
    second = app.post(url, json={"packet_hash": "a" * 64})
    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()
    assert [name for name, _ in calls] == [
        "get",
        "render",
        "register",
        "get",
        "download",
    ]
    saved = calls[2][1]
    assert saved["loan_id"] == loan_id and saved["actor_user_id"] == actor.user_id
    assert saved["registered_device_id"] == actor.registered_device_id
    assert saved["content"].startswith(b"%PDF-")


def test_download_is_authenticated_private_attachment_and_rechecks_persisted_access(
    monkeypatch,
):
    app, repository, _, _, _ = client(monkeypatch, role="employee")
    url = f"/api/v1/management/first-loans/{uuid4()}/documents"
    response = app.get(url)
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF-")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-disposition"].startswith("attachment;")
    assert response.headers["content-security-policy"] == "sandbox"

    def deny(**kwargs):
        raise FirstLoanAccessDenied("Revoked office access")

    repository.packet_document = deny
    response = app.get(url)
    assert (
        response.status_code == 403 and response.headers["cache-control"] == "no-store"
    )
