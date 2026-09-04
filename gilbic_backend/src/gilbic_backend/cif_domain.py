from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from hashlib import sha256
from typing import Literal
from uuid import UUID


CifLifecycleState = Literal["draft", "active", "superseded"]
CifPublicStatus = Literal["Draft", "Active", "Expiring", "Expired", "Superseded"]

ALLOWED_REVERIFICATION_REASONS = frozenset(
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
ALLOWED_EVIDENCE_TYPES = frozenset(
    {
        "national_id_check",
        "government_id_metadata",
        "utility_proof",
        "residence_visit",
        "approved_exception",
    }
)
ALLOWED_ACCESS_PURPOSES = frozenset(
    {
        "cif_verification",
        "cif_reverification",
        "compliance_review",
        "dpo_audit",
    }
)

_UNMASKED_NUMBER = re.compile(r"\d{6,}")


def _require_aware(value: datetime, *, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware.")


def five_year_expiry(effective_at: datetime) -> datetime:
    """Return the same local timestamp five calendar years later.

    February 29 expires on February 28 when the fifth year is not a leap year,
    matching PostgreSQL's calendar-year interval behavior.
    """

    _require_aware(effective_at, name="effective_at")
    try:
        return effective_at.replace(year=effective_at.year + 5)
    except ValueError:
        return effective_at.replace(year=effective_at.year + 5, month=2, day=28)


def derive_cif_public_status(
    *,
    lifecycle_state: str,
    effective_at: datetime | None,
    expires_at: datetime | None,
    as_of: datetime,
) -> CifPublicStatus:
    """Derive the current display state without mutating the stored CIF row."""

    _require_aware(as_of, name="as_of")
    normalized = lifecycle_state.strip().lower()
    if normalized == "draft":
        return "Draft"
    if normalized == "superseded":
        return "Superseded"
    if normalized != "active":
        raise ValueError("Unsupported CIF lifecycle state.")
    if effective_at is None or expires_at is None:
        raise ValueError("An active CIF requires effective_at and expires_at.")
    _require_aware(effective_at, name="effective_at")
    _require_aware(expires_at, name="expires_at")
    if expires_at <= effective_at:
        raise ValueError("expires_at must be later than effective_at.")
    if as_of < effective_at:
        return "Draft"
    if as_of >= expires_at:
        return "Expired"
    if as_of >= expires_at - timedelta(days=90):
        return "Expiring"
    return "Active"


def _json_default(value: object) -> object:
    if isinstance(value, datetime):
        _require_aware(value, name="datetime value")
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (set, frozenset, tuple)):
        return list(value)
    raise TypeError(f"Unsupported canonical CIF value: {type(value).__name__}")


def canonical_cif_digest(payload: Mapping[str, object]) -> str:
    """Return a deterministic SHA-256 digest for ordinary CIF source fields."""

    encoded = json.dumps(
        dict(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=_json_default,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def normalize_masked_reference(value: str) -> str:
    """Validate a display-safe reference without accepting full numeric IDs."""

    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError("Masked references cannot contain control characters.")
    normalized = value.strip()
    if not normalized:
        raise ValueError("A masked reference is required.")
    if len(normalized) > 120:
        raise ValueError("A masked reference cannot exceed 120 characters.")
    if _UNMASKED_NUMBER.search(normalized):
        raise ValueError("The reference must remain masked and cannot contain a full number.")
    return normalized
