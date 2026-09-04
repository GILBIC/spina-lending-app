from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from gilbic_backend.restricted_identity_api import (
    RestrictedEvidenceRequest,
    _evidence_payload,
    create_restricted_identity_router,
)
from gilbic_backend.restricted_identity_repository import (
    RestrictedEvidenceRecord,
)


EVIDENCE_ID = UUID("11111111-1111-1111-1111-111111111111")
CIF_ID = UUID("22222222-2222-2222-2222-222222222222")
CLIENT_ID = UUID("33333333-3333-3333-3333-333333333333")
ACTOR_ID = UUID("44444444-4444-4444-4444-444444444444")


def _record() -> RestrictedEvidenceRecord:
    now = datetime(2026, 9, 4, tzinfo=UTC)
    return RestrictedEvidenceRecord(
        evidence_id=EVIDENCE_ID,
        cif_id=CIF_ID,
        client_id=CLIENT_ID,
        evidence_type="national_id_check",
        verification_method="National ID Check",
        verification_result="verified",
        checked_at=now,
        document_date=date(2026, 8, 20),
        document_expires_at=None,
        masked_reference="****-****-1234",
        external_evidence_reference="restricted/evidence/example",
        evidence_sha256="a" * 64,
        retention_class="identity_verification",
        retain_until=date(2031, 9, 4),
        legal_hold=False,
        review_state="verified",
        verified_by_user_id=ACTOR_ID,
        final_reviewed_by_user_id=UUID(
            "55555555-5555-5555-5555-555555555555"
        ),
        reviewed_at=now,
        supersedes_evidence_id=None,
        created_by_user_id=ACTOR_ID,
        created_at=now,
    )


def test_restricted_request_forbids_raw_or_unexpected_fields() -> None:
    base = {
        "evidence_type": "national_id_check",
        "verification_method": "National ID Check",
        "verification_result": "verified",
        "checked_at": "2026-09-04T00:00:00Z",
        "masked_reference": "****1234",
        "external_evidence_reference": "restricted/example",
        "evidence_sha256": "a" * 64,
        "retention_class": "identity_verification",
        "retain_until": "2031-09-04",
    }
    for forbidden in (
        "raw_document",
        "national_id_number",
        "otp",
        "mpin",
        "password",
        "provider_payload",
        "phone_contacts",
    ):
        with pytest.raises(ValidationError):
            RestrictedEvidenceRequest.model_validate(
                {**base, forbidden: "not allowed"}
            )


def test_restricted_payload_is_explicit_metadata_only() -> None:
    payload = _evidence_payload(_record())
    flattened = str(payload).lower()

    assert payload["evidence_id"] == str(EVIDENCE_ID)
    assert payload["masked_reference"] == "****-****-1234"
    for forbidden in (
        "raw_document",
        "document_bytes",
        "otp",
        "mpin",
        "password",
        "provider_payload",
        "phone_contacts",
        "full_national_id",
    ):
        assert forbidden not in flattened


def test_restricted_router_exposes_only_management_endpoints() -> None:
    routes = {
        (route.path, method)
        for route in create_restricted_identity_router().routes
        for method in (route.methods or set())
    }

    assert (
        "/api/v1/management/cifs/{cif_id}/verification-evidence",
        "GET",
    ) in routes
    assert (
        "/api/v1/management/cifs/{cif_id}/verification-evidence",
        "POST",
    ) in routes
    assert (
        "/api/v1/management/verification-evidence/{evidence_id}/review",
        "POST",
    ) in routes
    assert (
        "/api/v1/management/verification-evidence/{evidence_id}/supersede",
        "POST",
    ) in routes
