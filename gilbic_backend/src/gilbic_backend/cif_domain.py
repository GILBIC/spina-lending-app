from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum


class CifDomainError(ValueError):
    """Raised when a CIF lifecycle snapshot is internally inconsistent."""


class CifDurableState(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUPERSEDED = "superseded"


class CifPublicStatus(StrEnum):
    DRAFT = "Draft"
    ACTIVE = "Active"
    EXPIRING = "Expiring"
    EXPIRED = "Expired"
    SUPERSEDED = "Superseded"


@dataclass(frozen=True, slots=True)
class CifEvaluation:
    public_status: CifPublicStatus
    is_eligible_for_new_credit: bool
    reverification_required: bool
    effective_at: datetime | None
    expires_at: datetime | None


def _require_aware(value: datetime, *, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CifDomainError(f"{field} must be timezone-aware")


def add_five_years(value: datetime) -> datetime:
    """Return the five-year anniversary, clamping a leap day to February 28."""

    _require_aware(value, field="effective_at")
    try:
        return value.replace(year=value.year + 5)
    except ValueError:
        if value.month == 2 and value.day == 29:
            return value.replace(year=value.year + 5, day=28)
        raise


def evaluate_cif(
    *,
    durable_state: CifDurableState,
    effective_at: datetime | None,
    expires_at: datetime | None,
    now: datetime,
    has_open_reverification: bool,
) -> CifEvaluation:
    """Derive the public status and new-credit eligibility from durable facts."""

    _require_aware(now, field="now")

    if durable_state is CifDurableState.DRAFT:
        if effective_at is not None or expires_at is not None:
            raise CifDomainError("draft CIF must not have effective or expiry timestamps")
        return CifEvaluation(
            public_status=CifPublicStatus.DRAFT,
            is_eligible_for_new_credit=False,
            reverification_required=has_open_reverification,
            effective_at=None,
            expires_at=None,
        )

    if effective_at is None or expires_at is None:
        raise CifDomainError("active or superseded CIF requires effective and expiry timestamps")
    _require_aware(effective_at, field="effective_at")
    _require_aware(expires_at, field="expires_at")

    if expires_at != add_five_years(effective_at):
        raise CifDomainError("CIF expiry must be exactly five years after effective_at")

    if durable_state is CifDurableState.SUPERSEDED:
        return CifEvaluation(
            public_status=CifPublicStatus.SUPERSEDED,
            is_eligible_for_new_credit=False,
            reverification_required=has_open_reverification,
            effective_at=effective_at,
            expires_at=expires_at,
        )

    if durable_state is not CifDurableState.ACTIVE:
        raise CifDomainError(f"unsupported CIF durable state: {durable_state!r}")

    if now >= expires_at:
        public_status = CifPublicStatus.EXPIRED
    elif now >= expires_at - timedelta(days=90):
        public_status = CifPublicStatus.EXPIRING
    else:
        public_status = CifPublicStatus.ACTIVE

    return CifEvaluation(
        public_status=public_status,
        is_eligible_for_new_credit=(
            public_status in {CifPublicStatus.ACTIVE, CifPublicStatus.EXPIRING}
            and not has_open_reverification
        ),
        reverification_required=has_open_reverification,
        effective_at=effective_at,
        expires_at=expires_at,
    )


def allows_existing_obligation_servicing(_: CifPublicStatus) -> bool:
    """CIF state never blocks payment, correction, reversal, or remittance."""

    return True
