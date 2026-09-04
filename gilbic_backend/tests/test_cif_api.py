from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from gilbic_backend.cif_api import (
    CifDraftRequest,
    _cif_payload,
    create_cif_router,
)
from gilbic_backend.cif_domain import CifDurableState
from gilbic_backend.cif_repository import CifRecord


ACTOR_ID = UUID("11111111-1111-1111-1111-111111111111")
CLIENT_ID = UUID("22222222-2222-2222-2222-222222222222")
CIF_ID = UUID("33333333-3333-3333-3333-333333333333")


def _record() -> CifRecord:
    now = datetime(2026, 9, 4, tzinfo=UTC)
    return CifRecord(
        cif_id=CIF_ID,
        cif_number="CIF-0000000001",
        client_id=CLIENT_ID,
        form_version=1,
        durable_state=CifDurableState.ACTIVE,
        public_status="Active",
        is_eligible_for_new_credit=True,
        reverification_required=False,
        allows_existing_obligation_servicing=True,
        effective_at=now,
        expires_at=datetime(2031, 9, 4, tzinfo=UTC),
        supersedes_cif_id=None,
        legal_full_name="Maria Dela Cruz",
        birth_date=date(1990, 5, 4),
        nationality="Filipino",
        civil_status="Married",
        phone_number="09171234567",
        email="maria@example.com",
        present_address={"barangay": "San Roque"},
        permanent_address={"barangay": "San Roque"},
        livelihood_profile={"occupation": "Store owner"},
        privacy_notice_version="privacy-v1",
        privacy_acknowledged_at=now,
        client_signature_reference="signatures/cif/example",
        client_signature_sha256="a" * 64,
        prepared_by_user_id=ACTOR_ID,
        verified_by_user_id=ACTOR_ID,
        verified_at=now,
        approved_by_user_id=UUID(
            "44444444-4444-4444-4444-444444444444"
        ),
        approved_at=now,
        content_digest_sha256="b" * 64,
        form_schema_version="cif-v1",
        draft_revision=1,
        created_at=now,
        updated_at=now,
    )


def test_ordinary_cif_payload_excludes_restricted_evidence() -> None:
    payload = _cif_payload(_record())
    flattened = str(payload).lower()

    assert payload["cif_id"] == str(CIF_ID)
    assert payload["status"] == "Active"
    assert payload["allows_existing_obligation_servicing"] is True
    for forbidden in (
        "utility_proof",
        "residence_visit",
        "evidence_sha256",
        "verification_result",
        "national_id",
        "raw_document",
    ):
        assert forbidden not in flattened


def test_cif_draft_request_forbids_unexpected_sensitive_fields() -> None:
    with pytest.raises(ValidationError):
        CifDraftRequest.model_validate(
            {
                "legal_full_name": "Maria Dela Cruz",
                "privacy_notice_version": "privacy-v1",
                "present_address": {"barangay": "San Roque"},
                "raw_national_id": "not allowed",
            }
        )


def test_cif_router_exposes_only_expected_management_mutations() -> None:
    routes = {
        (route.path, method)
        for route in create_cif_router().routes
        for method in (route.methods or set())
    }

    assert ("/api/v1/management/clients/{client_id}/cifs", "GET") in routes
    assert ("/api/v1/management/clients/{client_id}/cifs", "POST") in routes
    assert ("/api/v1/management/cifs/{cif_id}", "GET") in routes
    assert ("/api/v1/management/cifs/{cif_id}", "PATCH") in routes
    assert ("/api/v1/management/cifs/{cif_id}/verify", "POST") in routes
    assert ("/api/v1/management/cifs/{cif_id}/activate", "POST") in routes
    assert (
        "/api/v1/management/clients/{client_id}/cif-reverification",
        "POST",
    ) in routes
