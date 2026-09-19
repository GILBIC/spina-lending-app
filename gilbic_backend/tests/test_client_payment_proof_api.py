"""Protected payment-proof transport, separate from official payment posting."""

from base64 import b64encode
from importlib import import_module
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

PDF = b"%PDF-1.4\nSynthetic proof\n%%EOF"
HEADERS = {"Authorization": "Bearer synthetic", "X-Device-Id": "proof-device"}


def setup(monkeypatch, role="client", permission=True, device=True):
    try:
        module = import_module("gilbic_backend.client_payment_proof_api")
    except ModuleNotFoundError:
        pytest.fail(
            "Protected Client payment-proof API is not implemented", pytrace=False
        )
    actor = SimpleNamespace(
        user_id=uuid4(),
        registered_device_id=uuid4() if device else None,
        roles=(role,),
        permissions=("client_payment_proof.review",) if permission else (),
    )

    def auth(**arguments):
        if not arguments["authorization"]:
            raise HTTPException(401, "Sign in required")
        if not arguments["device_identifier"]:
            raise HTTPException(400, "Device required")
        return actor

    monkeypatch.setattr(module, "authenticated_device_context", auth)

    class Repository:
        calls = None
        error = None

        def __init__(self):
            self.calls = []

        def __getattr__(self, name):
            def call(**arguments):
                self.calls.append((name, arguments))
                if self.error:
                    raise self.error
                if name == "content":
                    return {"media_type": "application/pdf"}, PDF
                if name == "list_proofs":
                    return {
                        "proofs": [],
                        "has_more": False,
                        "capability": {"posts_payment": False},
                    }
                return {
                    "proof": {
                        "status": "under_review",
                        "official_payment_posted": False,
                    },
                    "history": [],
                }

            return call

    repository = Repository()
    app = FastAPI()
    app.include_router(module.create_client_payment_proof_router())
    app.dependency_overrides[module.client_payment_proof_repository_dependency] = (
        lambda: repository
    )
    app.dependency_overrides[module.auth_client_dependency] = lambda: object()
    app.dependency_overrides[module.account_repository_dependency] = lambda: object()
    return TestClient(app), repository, actor, module


@pytest.mark.parametrize("prefix", ["/api/v1", "/api/mobile/v1"])
def test_upload_uses_real_bytes_and_authenticated_identity(monkeypatch, prefix):
    client, repository, actor, _ = setup(monkeypatch)
    loan_id, request_id = uuid4(), uuid4()
    response = client.post(
        prefix + "/client/payment-proofs",
        params={
            "loan_id": str(loan_id),
            "request_id": str(request_id),
        },
        headers={
            **HEADERS,
            "Content-Type": "application/pdf",
            "X-Proof-Note": b64encode("Resibo para kay José — ₱500".encode()).decode(),
        },
        content=PDF,
    )
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["data"]["proof"]["official_payment_posted"] is False
    name, arguments = repository.calls[-1]
    assert name == "upload"
    assert arguments["actor_user_id"] == actor.user_id
    assert arguments["registered_device_id"] == actor.registered_device_id
    assert arguments["loan_id"] == loan_id and arguments["request_id"] == request_id
    assert arguments["content"] == PDF
    assert arguments["note"] == "Resibo para kay José — ₱500"
    assert "note" not in response.request.url.params


@pytest.mark.parametrize("prefix", ["/api/v1", "/api/mobile/v1"])
def test_own_version_download_is_authenticated_and_private(monkeypatch, prefix):
    client, repository, actor, _ = setup(monkeypatch)
    proof_id = uuid4()
    response = client.get(
        prefix + f"/client/payment-proofs/{proof_id}/versions/1/content",
        headers=HEADERS,
    )
    assert response.status_code == 200 and response.content == PDF
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-security-policy"] == "sandbox"
    assert "attachment" in response.headers["content-disposition"]
    assert repository.calls[-1][1]["actor_user_id"] == actor.user_id
    assert repository.calls[-1][1]["management"] is False


@pytest.mark.parametrize(
    "role,permission,device,path,status",
    [
        ("client", True, True, "/management/payment-proofs", 403),
        ("employee", True, True, "/management/payment-proofs", 403),
        ("management", False, True, "/management/payment-proofs", 403),
        ("management", True, False, "/management/payment-proofs", 403),
        ("management", True, True, "/client/payment-proofs", 403),
        ("client", False, False, "/client/payment-proofs", 403),
    ],
)
def test_wrong_role_permission_or_device_never_reaches_repository(
    monkeypatch, role, permission, device, path, status
):
    client, repository, _, _ = setup(monkeypatch, role, permission, device)
    response = client.get("/api/v1" + path, headers=HEADERS)
    assert response.status_code == status
    assert response.headers["cache-control"] == "no-store"
    assert repository.calls == []


@pytest.mark.parametrize(
    "headers,status", [({}, 401), ({"Authorization": "Bearer synthetic"}, 400)]
)
def test_authentication_and_device_are_required(monkeypatch, headers, status):
    client, repository, _, _ = setup(monkeypatch)
    response = client.get("/api/v1/client/payment-proofs", headers=headers)
    assert response.status_code == status and repository.calls == []
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "media,content",
    [
        ("text/html", b"<script>x</script>"),
        ("image/png", PDF),
        ("application/pdf", b""),
    ],
)
def test_unacceptable_bytes_cannot_be_uploaded(monkeypatch, media, content):
    client, repository, _, _ = setup(monkeypatch)
    response = client.post(
        "/api/v1/client/payment-proofs",
        params={"loan_id": str(uuid4()), "request_id": str(uuid4())},
        headers={**HEADERS, "Content-Type": media},
        content=content,
    )
    assert response.status_code == 415 and repository.calls == []


@pytest.mark.parametrize("streamed", [False, True])
def test_upload_size_is_limited_with_or_without_content_length(monkeypatch, streamed):
    client, repository, _, module = setup(monkeypatch)
    monkeypatch.setattr(module, "MAX_EVIDENCE_BYTES", 10)
    response = client.post(
        "/api/v1/client/payment-proofs",
        params={"loan_id": str(uuid4()), "request_id": str(uuid4())},
        headers={**HEADERS, "Content-Type": "application/pdf"},
        content=iter([PDF[:10], PDF[10:]]) if streamed else PDF,
    )
    assert response.status_code == 413 and repository.calls == []


def test_reupload_passes_exact_previous_version_without_accepting_client_identity(
    monkeypatch,
):
    client, repository, actor, _ = setup(monkeypatch)
    proof_id, request_id = uuid4(), uuid4()
    response = client.post(
        f"/api/v1/client/payment-proofs/{proof_id}/versions",
        params={
            "request_id": str(request_id),
            "expected_version": 2,
            "client_id": str(uuid4()),
        },
        headers={**HEADERS, "Content-Type": "application/pdf"},
        content=PDF,
    )
    assert response.status_code == 201
    arguments = repository.calls[-1][1]
    assert (
        arguments["actor_user_id"] == actor.user_id
        and arguments["expected_version"] == 2
    )
    assert "client_id" not in arguments and "loan_id" not in arguments


@pytest.mark.parametrize("prefix", ["/api/v1", "/api/mobile/v1"])
def test_management_review_uses_current_version_and_review_identity(
    monkeypatch, prefix
):
    client, repository, actor, _ = setup(monkeypatch, "management")
    proof_id, request_id, review_id = uuid4(), uuid4(), uuid4()
    response = client.post(
        prefix + f"/management/payment-proofs/{proof_id}/reviews",
        headers=HEADERS,
        json={
            "request_id": str(request_id),
            "expected_version": 2,
            "expected_review_id": str(review_id),
            "decision": "correction_required",
            "reason": "Upload the complete receipt",
        },
    )
    assert response.status_code == 201
    arguments = repository.calls[-1][1]
    assert arguments["actor_user_id"] == actor.user_id
    assert (
        arguments["expected_version"] == 2
        and arguments["expected_review_id"] == review_id
    )
    assert arguments["decision"] == "correction_required"


@pytest.mark.parametrize(
    "change",
    [
        {"decision": "paid"},
        {"official_payment_posted": True},
        {"expected_version": True},
    ],
)
def test_review_cannot_introduce_payment_authority(monkeypatch, change):
    client, repository, _, _ = setup(monkeypatch, "management")
    payload = {
        "request_id": str(uuid4()),
        "expected_version": 1,
        "expected_review_id": None,
        "decision": "reviewed",
        **change,
    }
    response = client.post(
        f"/api/v1/management/payment-proofs/{uuid4()}/reviews",
        headers=HEADERS,
        json=payload,
    )
    assert response.status_code == 422 and repository.calls == []


@pytest.mark.parametrize(
    "error_name,status",
    [
        ("PaymentProofAccessDenied", 403),
        ("PaymentProofNotFound", 404),
        ("PaymentProofConflict", 409),
        ("PaymentProofInvalid", 422),
        ("EvidenceFileError", 503),
    ],
)
def test_domain_failures_are_private_and_controlled(monkeypatch, error_name, status):
    client, repository, _, module = setup(monkeypatch)
    repository.error = getattr(module, error_name)("Synthetic sensitive storage path")
    response = client.get(f"/api/v1/client/payment-proofs/{uuid4()}", headers=HEADERS)
    assert response.status_code == status
    assert response.headers["cache-control"] == "no-store"
    if status in (403, 404, 503):
        assert "sensitive storage" not in response.text


def test_note_and_request_identity_validation(monkeypatch):
    client, repository, _, _ = setup(monkeypatch)
    response = client.post(
        "/api/v1/client/payment-proofs",
        params={
            "loan_id": str(uuid4()),
            "request_id": "not-a-uuid",
        },
        headers={**HEADERS, "Content-Type": "application/pdf"},
        content=PDF,
    )
    assert response.status_code == 422 and repository.calls == []


@pytest.mark.parametrize(
    "note_header",
    ["not base64!", "wA==", b64encode(("é" * 1001).encode()).decode(), "YQ==\n"],
)
@pytest.mark.parametrize("revision", [False, True])
def test_invalid_note_headers_fail_without_echoing_private_input(
    monkeypatch, note_header, revision
):
    client, repository, _, _ = setup(monkeypatch)
    path = "/api/v1/client/payment-proofs"
    params = {"request_id": str(uuid4())}
    if revision:
        path += f"/{uuid4()}/versions"
        params["expected_version"] = 1
    else:
        params["loan_id"] = str(uuid4())
    response = client.post(
        path,
        params=params,
        headers={
            **HEADERS,
            "Content-Type": "application/pdf",
            "X-Proof-Note": note_header,
        },
        content=PDF,
    )
    assert response.status_code == 422 and repository.calls == []
    assert response.headers["cache-control"] == "no-store"
    assert (
        response.json()["detail"]
        == "Payment-proof note must be valid UTF-8 text of at most 1000 characters."
    )


def test_upload_schema_keeps_free_text_out_of_query_parameters(monkeypatch):
    client, _, _, _ = setup(monkeypatch)
    paths = client.get("/openapi.json").json()["paths"]
    for path in (
        "/api/v1/client/payment-proofs",
        "/api/v1/client/payment-proofs/{proof_id}/versions",
    ):
        parameters = paths[path]["post"]["parameters"]
        assert not any(p["name"] == "note" and p["in"] == "query" for p in parameters)
        assert any(
            p["name"] == "X-Proof-Note" and p["in"] == "header" for p in parameters
        )


def test_reviewed_evidence_accepts_an_empty_reason(monkeypatch):
    client, repository, _, _ = setup(monkeypatch, "management")
    response = client.post(
        f"/api/v1/management/payment-proofs/{uuid4()}/reviews",
        headers=HEADERS,
        json={
            "request_id": str(uuid4()),
            "expected_version": 1,
            "expected_review_id": None,
            "decision": "reviewed",
            "reason": "",
        },
    )
    assert response.status_code == 201
    assert repository.calls[-1][1]["reason"] == ""


def test_capability_requires_private_storage_and_does_not_claim_payment(
    monkeypatch, tmp_path
):
    from gilbic_backend.client_payment_proof_repository import payment_proof_capability

    monkeypatch.delenv("GILBIC_OFFICE_REVIEW_EVIDENCE_ROOT", raising=False)
    assert payment_proof_capability()["upload_available"] is False
    monkeypatch.setenv("GILBIC_OFFICE_REVIEW_EVIDENCE_ROOT", str(tmp_path / "private"))
    capability = payment_proof_capability()
    assert (
        capability["upload_available"] is True and capability["posts_payment"] is False
    )
    assert capability["max_bytes"] == 10 * 1024 * 1024
    assert capability["allowed_media_types"] == [
        "application/pdf",
        "image/jpeg",
        "image/png",
    ]
