from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
import test_client_cif_review_summary_api as summary
from gilbic_backend.office_review_evidence_api import (
    office_review_evidence_repository_dependency,
)
from gilbic_backend.office_review_evidence_repository import (
    OfficeReviewEvidenceConflict,
)
from office_review_evidence_test_support import PDF

BASE = f"/api/v1/management/clients/{summary.CLIENT_ID}/review-evidence"
SOURCE = f"purpose=cif_review&cif_version_id={summary.CIF_ID}"


class Repository:
    def __init__(self):
        self.calls = []
        self.error = None

    def get_context(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return {
            "client_id": str(summary.CLIENT_ID),
            "cif_version_id": str(summary.CIF_ID),
            "snapshot_sha256": "a" * 64,
        }

    def capture(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        self.record = SimpleNamespace(
            id=uuid4(),
            client_id=summary.CLIENT_ID,
            cif_version_id=summary.CIF_ID,
            application_id=None,
            application_version_id=None,
            purpose="cif_review",
            snapshot_sha256="a" * 64,
            content_sha256="b" * 64,
            media_type="application/pdf",
            byte_count=len(PDF),
            captured_by_user_id=summary.ACTOR_ID,
            captured_at=datetime(2026, 9, 19, tzinfo=timezone.utc),
            private_path="NEVER-RETURN",
        )
        self.record.evidence_reference = f"office-evidence:{self.record.id}"
        return self.record

    def get_content(self, **kwargs):
        self.calls.append(kwargs)
        return self.record, PDF


def client(**kwargs):
    http, _ = summary._client(**kwargs)
    repository = Repository()
    http.app.dependency_overrides[office_review_evidence_repository_dependency] = (
        lambda: repository
    )
    return http, repository


def upload(http, **kwargs):
    return http.post(
        f"{BASE}?{SOURCE}&request_id={uuid4()}&expected_snapshot_sha256={'a' * 64}&witnessed_wet_signature=true",
        headers={**summary.HEADERS, "Content-Type": "application/pdf"},
        content=PDF,
        **kwargs,
    )


@pytest.mark.parametrize("role", ["employee", "management"])
def test_capture_delegates_actual_file_and_download_is_authenticated_attachment(role):
    http, repository = client(role=role)
    response = upload(http)
    assert response.status_code == 201, response.text
    assert response.headers["cache-control"] == "no-store"
    assert repository.calls[0]["content"] == PDF
    assert repository.calls[0]["actor_user_id"] == summary.ACTOR_ID
    assert "private_path" not in response.json()
    record = response.json()
    download = http.get(f"{BASE}/{record['evidence_id']}", headers=summary.HEADERS)
    assert download.content == PDF
    assert download.headers["content-disposition"].startswith("attachment;")
    assert download.headers["cache-control"] == "no-store"
    assert download.headers["x-content-type-options"] == "nosniff"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"role": "collector"},
        {"role": "client"},
        {"role": "unknown"},
        {"permissions": ()},
        {"account_error": "AccountDisabled"},
        {"account_error": "DeviceRevoked"},
        {"account_error": "DeviceNotRegistered"},
    ],
)
def test_capture_and_context_reject_non_authorized_accounts_without_repository(kwargs):
    http, repository = client(**kwargs)
    assert upload(http).status_code == 403
    assert (
        http.get(f"{BASE}/context?{SOURCE}", headers=summary.HEADERS).status_code == 403
    )
    assert repository.calls == []


@pytest.mark.parametrize(
    "content,media,status",
    [
        (b"not a signed scan", "application/pdf", 415),
        (b"<svg/>", "image/svg+xml", 415),
        (b"", "application/pdf", 415),
    ],
)
def test_capture_rejects_invalid_file_without_persistence(content, media, status):
    http, repository = client()
    response = http.post(
        f"{BASE}?{SOURCE}&request_id={uuid4()}&expected_snapshot_sha256={'a' * 64}&witnessed_wet_signature=true",
        headers={**summary.HEADERS, "Content-Type": media},
        content=content,
    )
    assert response.status_code == status
    assert response.headers["cache-control"] == "no-store"
    assert repository.calls == []


def test_missing_witness_attestation_and_changed_snapshot_are_not_captured():
    http, repository = client()
    response = http.post(
        f"{BASE}?{SOURCE}&request_id={uuid4()}&expected_snapshot_sha256={'a' * 64}",
        headers=summary.HEADERS,
        content=PDF,
    )
    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"
    assert repository.calls == []
    repository.error = OfficeReviewEvidenceConflict(
        "Review changed; refresh before capturing signed evidence."
    )
    assert upload(http).status_code == 409
