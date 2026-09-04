from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from gilbic_backend.cif_domain import (
    ALLOWED_ACCESS_PURPOSES,
    ALLOWED_EVIDENCE_TYPES,
    ALLOWED_REVERIFICATION_REASONS,
    canonical_cif_digest,
    derive_cif_public_status,
    five_year_expiry,
    normalize_masked_reference,
)


NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def test_derives_all_public_cif_states_without_background_mutation() -> None:
    assert derive_cif_public_status(
        lifecycle_state="draft",
        effective_at=None,
        expires_at=None,
        as_of=NOW,
    ) == "Draft"
    assert derive_cif_public_status(
        lifecycle_state="active",
        effective_at=NOW - timedelta(days=1),
        expires_at=NOW + timedelta(days=91),
        as_of=NOW,
    ) == "Active"
    assert derive_cif_public_status(
        lifecycle_state="active",
        effective_at=NOW - timedelta(days=1),
        expires_at=NOW + timedelta(days=90),
        as_of=NOW,
    ) == "Expiring"
    assert derive_cif_public_status(
        lifecycle_state="active",
        effective_at=NOW - timedelta(days=400),
        expires_at=NOW,
        as_of=NOW,
    ) == "Expired"
    assert derive_cif_public_status(
        lifecycle_state="superseded",
        effective_at=NOW - timedelta(days=400),
        expires_at=NOW + timedelta(days=400),
        as_of=NOW,
    ) == "Superseded"


def test_active_cif_cannot_have_missing_activation_timestamps() -> None:
    with pytest.raises(ValueError, match="effective_at and expires_at"):
        derive_cif_public_status(
            lifecycle_state="active",
            effective_at=None,
            expires_at=None,
            as_of=NOW,
        )


def test_five_year_expiry_handles_leap_day_as_calendar_years() -> None:
    effective = datetime(2024, 2, 29, 8, 30, tzinfo=UTC)

    assert five_year_expiry(effective) == datetime(2029, 2, 28, 8, 30, tzinfo=UTC)


def test_canonical_digest_is_stable_across_mapping_order_and_dates() -> None:
    first = {
        "legal_full_name": "Client One",
        "birth_date": date(1990, 1, 2),
        "present_address": {"province": "Rizal", "barangay": "San Juan"},
    }
    second = {
        "present_address": {"barangay": "San Juan", "province": "Rizal"},
        "birth_date": date(1990, 1, 2),
        "legal_full_name": "Client One",
    }

    digest = canonical_cif_digest(first)

    assert digest == canonical_cif_digest(second)
    assert len(digest) == 64
    assert digest == digest.lower()


def test_masked_reference_rejects_unmasked_number_and_control_characters() -> None:
    with pytest.raises(ValueError, match="masked"):
        normalize_masked_reference("123456789012")
    with pytest.raises(ValueError, match="control"):
        normalize_masked_reference("****-1234\n")


def test_masked_reference_accepts_safe_display_value() -> None:
    assert normalize_masked_reference("  ****-****-1234  ") == "****-****-1234"


def test_policy_allowlists_are_exact_and_do_not_admit_free_form_values() -> None:
    assert ALLOWED_REVERIFICATION_REASONS == frozenset(
        {
            "material_identity_change",
            "address_change",
            "contact_change",
            "document_expiry",
            "discrepancy",
            "suspicious_activity",
            "approved_risk_event",
        }
    )
    assert ALLOWED_EVIDENCE_TYPES == frozenset(
        {
            "national_id_check",
            "government_id_metadata",
            "utility_proof",
            "residence_visit",
            "approved_exception",
        }
    )
    assert ALLOWED_ACCESS_PURPOSES == frozenset(
        {
            "cif_verification",
            "cif_reverification",
            "compliance_review",
            "dpo_audit",
        }
    )
