"""The real office auth/device boundary protects privacy reads and acknowledgment."""

from uuid import UUID

import pytest

from gilbic_backend import privacy_record_api as module
from gilbic_backend.privacy_record_repository import privacy_package
from test_client_onboarding_cif_selection_api import (
    ACTOR_ID,
    CLIENT_ID,
    HEADERS,
    _client,
)
from test_privacy_records import configure

CIF = UUID("44444444-4444-4444-8444-444444444444")
BASE = f"/api/v1/management/clients/{CLIENT_ID}/privacy"
PERMISSION = "client_onboarding.requirement.review"


def client(**options):
    http, _ = _client(**options)

    class Repository:
        def __init__(self):
            self.calls = []

        def context(self, **arguments):
            self.calls.append(("context", arguments))
            package = privacy_package()
            return {
                "client_id": str(CLIENT_ID),
                "cif_version_id": str(CIF),
                "issuable": package["issuable"],
                "detail": "Synthetic document state",
                "review_snapshot": {
                    kind: {"sha256": package[kind]["sha256"]}
                    for kind in ("notice", "consent")
                    if package["issuable"]
                },
            }

        def confirm(self, **arguments):
            self.calls.append(("confirm", arguments))
            return {"recorded": True}

    repository = Repository()
    http.app.dependency_overrides[module.privacy_repository_dependency] = lambda: (
        repository
    )
    return http, repository


def request(http, operation, headers=HEADERS, digest="a" * 64):
    if operation == "context":
        return http.get(f"{BASE}/context?cif_version_id={CIF}", headers=headers)
    if operation == "document":
        return http.get(
            f"{BASE}/documents/notice?cif_version_id={CIF}&expected_sha256={digest}",
            headers=headers,
        )
    return http.post(
        f"{BASE}/acknowledgments",
        headers=headers,
        json={
            "cif_version_id": str(CIF),
            "optional_service_communications": False,
            "evidence_reference": "office-evidence:55555555-5555-4555-8555-555555555555",
        },
    )


@pytest.mark.parametrize("role", ["employee", "management"])
def test_authorized_privacy_reads_capture_persisted_actor_and_exact_optional_false(
    tmp_path, monkeypatch, role
):
    configure(tmp_path, monkeypatch)
    http, repository = client(role=role)
    result = request(http, "context")
    assert result.status_code == 200 and result.headers["cache-control"] == "no-store"
    assert repository.calls == [
        (
            "context",
            {
                "actor_user_id": ACTOR_ID,
                "client_id": CLIENT_ID,
                "cif_version_id": CIF,
                "optional_service_communications": False,
            },
        )
    ]
    result = request(http, "acknowledgment")
    assert result.status_code == 201 and result.headers["cache-control"] == "no-store"
    assert repository.calls[-1][1]["actor_user_id"] == ACTOR_ID
    assert repository.calls[-1][1]["optional_service_communications"] is False


@pytest.mark.parametrize("operation", ["context", "document", "acknowledgment"])
@pytest.mark.parametrize(
    "role,permissions",
    [
        ("collector", (PERMISSION,)),
        ("client", (PERMISSION,)),
        ("employee", ()),
        ("management", (PERMISSION + ".extra",)),
    ],
)
def test_every_privacy_route_requires_exact_office_role_and_permission(
    operation, role, permissions
):
    http, repository = client(role=role, permissions=permissions)
    result = request(http, operation)
    assert result.status_code == 403 and result.headers["cache-control"] == "no-store"
    assert repository.calls == []


@pytest.mark.parametrize("headers", [{}, {"Authorization": HEADERS["Authorization"]}])
def test_private_document_never_reaches_repository_without_authentication_and_device(
    headers,
):
    http, repository = client()
    result = request(http, "document", headers)
    assert (
        result.status_code in (400, 401)
        and result.headers["cache-control"] == "no-store"
    )
    assert repository.calls == []


@pytest.mark.parametrize("operation", ["context", "document", "acknowledgment"])
def test_revoked_registered_device_blocks_privacy_operation(operation):
    http, repository = client(account_error="DeviceRevoked")
    result = request(http, operation)
    assert result.status_code == 403 and result.headers["cache-control"] == "no-store"
    assert repository.calls == []


def test_document_download_returns_exact_bytes_with_private_response_headers(
    tmp_path, monkeypatch
):
    _, _, pdf = configure(tmp_path, monkeypatch)
    http, repository = client()
    result = request(http, "document", digest=privacy_package()["notice"]["sha256"])
    assert result.status_code == 200
    assert result.content == pdf.read_bytes()
    assert result.headers["cache-control"] == "no-store"
    assert result.headers["content-type"] == "application/pdf"
    assert result.headers["x-content-type-options"] == "nosniff"
    assert result.headers["content-security-policy"] == "sandbox"
    assert "attachment" in result.headers["content-disposition"]
    assert repository.calls[0][1]["actor_user_id"] == ACTOR_ID


@pytest.mark.parametrize("digest", [None, "invalid", "A" * 64])
def test_download_requires_the_exact_displayed_digest_before_serving_bytes(digest):
    http, repository = client()
    suffix = "" if digest is None else f"&expected_sha256={digest}"
    result = http.get(
        f"{BASE}/documents/notice?cif_version_id={CIF}{suffix}", headers=HEADERS
    )
    assert result.status_code == 422 and result.headers["cache-control"] == "no-store"
    assert repository.calls == []
