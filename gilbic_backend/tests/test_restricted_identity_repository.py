from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from gilbic_backend.restricted_identity_repository import (
    RestrictedEvidenceInput,
    RestrictedEvidenceValidationError,
    normalize_masked_reference,
    validate_restricted_evidence,
)


def _evidence(**changes: object) -> RestrictedEvidenceInput:
    values: dict[str, object] = {
        "evidence_type": "national_id_check",
        "verification_method": "National ID Check",
        "verification_result": "verified",
        "checked_at": datetime(2026, 9, 4, tzinfo=UTC),
        "document_date": date(2026, 8, 20),
        "document_expires_at": None,
        "masked_reference": "****-****-1234",
        "external_evidence_reference": "restricted/cif/example/evidence-1",
        "evidence_sha256": "b" * 64,
        "retention_class": "identity_verification",
        "retain_until": date(2031, 9, 4),
        "legal_hold": False,
    }
    values.update(changes)
    return RestrictedEvidenceInput(**values)  # type: ignore[arg-type]


def test_validation_normalizes_allowlisted_metadata_only() -> None:
    result = validate_restricted_evidence(_evidence())

    assert result.evidence_type == "national_id_check"
    assert result.verification_method == "National ID Check"
    assert result.masked_reference == "****-****-1234"
    assert result.external_evidence_reference == (
        "restricted/cif/example/evidence-1"
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("evidence_type", "selfie_dump"),
        ("verification_result", "maybe"),
        ("retention_class", "forever"),
    ],
)
def test_validation_rejects_unknown_policy_values(
    field: str,
    value: str,
) -> None:
    with pytest.raises(RestrictedEvidenceValidationError, match="unsupported"):
        validate_restricted_evidence(_evidence(**{field: value}))


def test_validation_rejects_non_sha256_digest() -> None:
    with pytest.raises(RestrictedEvidenceValidationError, match="SHA-256"):
        validate_restricted_evidence(_evidence(evidence_sha256="ABC"))


def test_validation_rejects_naive_checked_timestamp() -> None:
    with pytest.raises(
        RestrictedEvidenceValidationError,
        match="timezone-aware",
    ):
        validate_restricted_evidence(
            _evidence(checked_at=datetime(2026, 9, 4))
        )


def test_masked_reference_rejects_apparent_unmasked_long_number() -> None:
    with pytest.raises(
        RestrictedEvidenceValidationError,
        match="masked",
    ):
        normalize_masked_reference("1234-5678-9012-3456")


def test_masked_reference_allows_short_safe_suffix() -> None:
    assert normalize_masked_reference("***1234") == "***1234"


def test_raw_bytes_are_not_accepted_as_external_reference() -> None:
    with pytest.raises(
        RestrictedEvidenceValidationError,
        match="text reference",
    ):
        validate_restricted_evidence(
            _evidence(external_evidence_reference=b"raw document")
        )


def test_retention_date_cannot_precede_evidence_date() -> None:
    with pytest.raises(
        RestrictedEvidenceValidationError,
        match="retention",
    ):
        validate_restricted_evidence(
            _evidence(retain_until=date(2026, 9, 3))
        )


def test_exception_evidence_is_marked_for_separate_review() -> None:
    result = validate_restricted_evidence(
        _evidence(
            evidence_type="approved_exception",
            verification_result="exception_approved",
            retention_class="exception_evidence",
        )
    )

    assert result.requires_separate_reviewer is True
