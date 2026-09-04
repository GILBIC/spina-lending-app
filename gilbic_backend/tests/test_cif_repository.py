from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from gilbic_backend.cif_repository import (
    CifDraftInput,
    CifValidationError,
    canonical_cif_digest,
    validate_cif_draft,
)


def _draft(**changes: object) -> CifDraftInput:
    values: dict[str, object] = {
        "legal_full_name": "  Maria Dela Cruz  ",
        "birth_date": date(1990, 5, 4),
        "nationality": " Filipino ",
        "civil_status": " Married ",
        "phone_number": " 09171234567 ",
        "email": " MARIA@example.com ",
        "present_address": {
            "line1": "12 Sampaguita Street",
            "barangay": "San Roque",
            "city_municipality": "Cardona",
            "province": "Rizal",
        },
        "permanent_address": {
            "line1": "12 Sampaguita Street",
            "barangay": "San Roque",
            "city_municipality": "Cardona",
            "province": "Rizal",
        },
        "livelihood_profile": {
            "occupation": "Store owner",
            "employer_business": "Maria Store",
        },
        "privacy_notice_version": "privacy-v1",
        "privacy_acknowledged_at": datetime(2026, 9, 4, tzinfo=UTC),
        "client_signature_reference": "signatures/cif/example",
        "client_signature_sha256": "a" * 64,
        "form_schema_version": "cif-v1",
    }
    values.update(changes)
    return CifDraftInput(**values)  # type: ignore[arg-type]


def test_validate_cif_draft_normalizes_safe_ordinary_fields() -> None:
    normalized = validate_cif_draft(_draft())

    assert normalized.legal_full_name == "Maria Dela Cruz"
    assert normalized.nationality == "Filipino"
    assert normalized.civil_status == "Married"
    assert normalized.phone_number == "09171234567"
    assert normalized.email == "maria@example.com"
    assert normalized.present_address["province"] == "Rizal"


def test_canonical_digest_is_stable_across_mapping_order() -> None:
    first = validate_cif_draft(_draft())
    second = validate_cif_draft(
        _draft(
            present_address={
                "province": "Rizal",
                "city_municipality": "Cardona",
                "barangay": "San Roque",
                "line1": "12 Sampaguita Street",
            }
        )
    )

    assert canonical_cif_digest(first) == canonical_cif_digest(second)


def test_canonical_digest_changes_when_source_content_changes() -> None:
    first = validate_cif_draft(_draft())
    second = validate_cif_draft(_draft(phone_number="09999999999"))

    assert canonical_cif_digest(first) != canonical_cif_digest(second)


def test_verifiable_draft_requires_address_privacy_and_signature_evidence() -> None:
    with pytest.raises(CifValidationError, match="present address"):
        validate_cif_draft(_draft(present_address={}), require_complete=True)
    with pytest.raises(CifValidationError, match="privacy acknowledgment"):
        validate_cif_draft(_draft(privacy_acknowledged_at=None), require_complete=True)
    with pytest.raises(CifValidationError, match="signature reference"):
        validate_cif_draft(_draft(client_signature_reference=None), require_complete=True)


def test_signature_digest_must_be_lowercase_sha256() -> None:
    with pytest.raises(CifValidationError, match="SHA-256"):
        validate_cif_draft(_draft(client_signature_sha256="ABC"), require_complete=True)


def test_ordinary_cif_mapping_rejects_sensitive_or_unbounded_keys() -> None:
    with pytest.raises(CifValidationError, match="unsupported address field"):
        validate_cif_draft(
            _draft(present_address={"line1": "Address", "document_photo": "data"})
        )
    with pytest.raises(CifValidationError, match="unsupported livelihood field"):
        validate_cif_draft(
            _draft(livelihood_profile={"occupation": "Seller", "provider_payload": {}})
        )
