from __future__ import annotations

from datetime import UTC, datetime

import pytest

from gilbic_backend.cif_domain import (
    CifDomainError,
    CifDurableState,
    CifPublicStatus,
    add_five_years,
    allows_existing_obligation_servicing,
    evaluate_cif,
)


def _utc(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=UTC)


def test_add_five_years_preserves_normal_calendar_date() -> None:
    assert add_five_years(_utc(2026, 9, 4)) == _utc(2031, 9, 4)


def test_add_five_years_clamps_leap_day_to_february_28() -> None:
    assert add_five_years(_utc(2024, 2, 29)) == _utc(2029, 2, 28)


def test_active_cif_becomes_expiring_exactly_ninety_days_before_expiry() -> None:
    effective_at = _utc(2026, 1, 1)
    expires_at = add_five_years(effective_at)

    before_boundary = evaluate_cif(
        durable_state=CifDurableState.ACTIVE,
        effective_at=effective_at,
        expires_at=expires_at,
        now=_utc(2030, 10, 2),
        has_open_reverification=False,
    )
    at_boundary = evaluate_cif(
        durable_state=CifDurableState.ACTIVE,
        effective_at=effective_at,
        expires_at=expires_at,
        now=_utc(2030, 10, 3),
        has_open_reverification=False,
    )

    assert before_boundary.public_status is CifPublicStatus.ACTIVE
    assert at_boundary.public_status is CifPublicStatus.EXPIRING
    assert at_boundary.is_eligible_for_new_credit is True


def test_active_cif_is_expired_at_expiry_instant() -> None:
    effective_at = _utc(2026, 9, 4)
    expires_at = add_five_years(effective_at)

    result = evaluate_cif(
        durable_state=CifDurableState.ACTIVE,
        effective_at=effective_at,
        expires_at=expires_at,
        now=expires_at,
        has_open_reverification=False,
    )

    assert result.public_status is CifPublicStatus.EXPIRED
    assert result.is_eligible_for_new_credit is False


def test_superseded_overrides_calendar_status() -> None:
    result = evaluate_cif(
        durable_state=CifDurableState.SUPERSEDED,
        effective_at=_utc(2020, 1, 1),
        expires_at=_utc(2025, 1, 1),
        now=_utc(2030, 1, 1),
        has_open_reverification=False,
    )

    assert result.public_status is CifPublicStatus.SUPERSEDED
    assert result.is_eligible_for_new_credit is False


def test_open_reverification_blocks_new_credit_without_rewriting_status() -> None:
    result = evaluate_cif(
        durable_state=CifDurableState.ACTIVE,
        effective_at=_utc(2026, 1, 1),
        expires_at=_utc(2031, 1, 1),
        now=_utc(2027, 1, 1),
        has_open_reverification=True,
    )

    assert result.public_status is CifPublicStatus.ACTIVE
    assert result.is_eligible_for_new_credit is False
    assert result.reverification_required is True


def test_draft_is_never_eligible() -> None:
    result = evaluate_cif(
        durable_state=CifDurableState.DRAFT,
        effective_at=None,
        expires_at=None,
        now=_utc(2026, 9, 4),
        has_open_reverification=False,
    )

    assert result.public_status is CifPublicStatus.DRAFT
    assert result.is_eligible_for_new_credit is False


def test_existing_obligation_servicing_never_depends_on_cif_status() -> None:
    for status in CifPublicStatus:
        assert allows_existing_obligation_servicing(status) is True


def test_active_state_requires_exact_five_year_expiry() -> None:
    with pytest.raises(CifDomainError, match="five years"):
        evaluate_cif(
            durable_state=CifDurableState.ACTIVE,
            effective_at=_utc(2026, 1, 1),
            expires_at=_utc(2030, 12, 31),
            now=_utc(2027, 1, 1),
            has_open_reverification=False,
        )


def test_datetimes_must_be_timezone_aware() -> None:
    with pytest.raises(CifDomainError, match="timezone-aware"):
        evaluate_cif(
            durable_state=CifDurableState.ACTIVE,
            effective_at=datetime(2026, 1, 1),
            expires_at=datetime(2031, 1, 1),
            now=datetime(2027, 1, 1),
            has_open_reverification=False,
        )
