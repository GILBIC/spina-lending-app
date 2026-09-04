from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

import gilbic_backend.cif_domain as cif_domain
from gilbic_backend.cif_repository import CifDraftData, CifInvalid, PostgresCifRepository
from gilbic_backend.restricted_identity_repository import (
    PostgresRestrictedIdentityRepository,
    RestrictedEvidenceData,
    RestrictedIdentityInvalid,
)


def _draft(*, signature_reference: str = "restricted-signature://client/1") -> CifDraftData:
    return CifDraftData(
        legal_full_name="Synthetic Client",
        birth_date=date(1990, 1, 2),
        place_of_birth="Rizal",
        nationality="Filipino",
        civil_status="single",
        phone_number="09170000000",
        email="synthetic@example.com",
        present_address={"line1": "Synthetic address"},
        permanent_address={"line1": "Synthetic address"},
        same_as_present_address=True,
        livelihood_profile={"kind": "self_employed", "description": "Synthetic"},
        privacy_notice_version="privacy-v1",
        privacy_acknowledged_at=datetime(2026, 9, 4, tzinfo=UTC),
        client_signature_reference=signature_reference,
        client_signature_digest="a" * 64,
        form_schema_version="1",
    )


def test_canonical_digest_orders_set_values_deterministically() -> None:
    values = {f"value-{index:02d}" for index in range(20)}

    assert cif_domain._json_default(values) == sorted(values)


def test_verification_rejects_structured_sections_with_only_empty_values() -> None:
    row = {
        "birth_date": date(1990, 1, 2),
        "nationality": "Filipino",
        "phone_number": "09170000000",
        "privacy_notice_version": "privacy-v1",
        "privacy_acknowledged_at": datetime(2026, 9, 4, tzinfo=UTC),
        "client_signature_reference": "restricted-signature://client/1",
        "client_signature_digest": "a" * 64,
        "same_as_present_address": False,
        "present_address": {"line1": "", "barangay": "", "province": ""},
        "permanent_address": {"line1": "", "barangay": "", "province": ""},
        "livelihood_profile": {"kind": "", "description": ""},
    }

    with pytest.raises(CifInvalid, match="present address"):
        PostgresCifRepository._assert_complete(row)


def test_same_as_present_normalization_copies_the_verified_address() -> None:
    draft = replace(
        _draft(),
        permanent_address={},
        same_as_present_address=True,
    )

    normalized = PostgresCifRepository._normalize_draft(draft)

    assert normalized.permanent_address == normalized.present_address


def test_signature_reference_rejects_inline_data_content() -> None:
    with pytest.raises(CifInvalid, match="inline data"):
        PostgresCifRepository._normalize_draft(
            _draft(signature_reference="data:image/png;base64,QUJDRA==")
        )


def test_restricted_evidence_reference_rejects_inline_data_content() -> None:
    data = RestrictedEvidenceData(
        evidence_type="national_id_check",
        verification_method="synthetic",
        verification_outcome="verified",
        checked_at=datetime(2026, 9, 4, tzinfo=UTC),
        document_date=date(2026, 9, 4),
        document_expires_at=None,
        masked_reference="****-****-1234",
        external_evidence_reference="data:application/pdf;base64,QUJDRA==",
        evidence_digest="b" * 64,
        retention_class="identity_verification",
        retain_until=date(2031, 9, 4),
        legal_hold=False,
        supersedes_evidence_id=None,
    )

    with pytest.raises(RestrictedIdentityInvalid, match="inline data"):
        PostgresRestrictedIdentityRepository._normalize_data(data)
