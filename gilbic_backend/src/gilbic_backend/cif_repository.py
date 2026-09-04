from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .cif_domain import (
    CifDurableState,
    CifEvaluation,
    add_five_years,
    evaluate_cif,
)
from .config import get_settings
from .database import normalize_database_url_for_psycopg


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ADDRESS_FIELDS = frozenset(
    {
        "line1",
        "line2",
        "barangay",
        "city_municipality",
        "province",
        "postal_code",
        "country",
    }
)
_LIVELIHOOD_FIELDS = frozenset(
    {
        "occupation",
        "employer_business",
        "business_address",
        "years_in_livelihood",
        "employment_type",
    }
)
_REVERIFICATION_REASONS = frozenset(
    {
        "material_identity_change",
        "address_change",
        "contact_change",
        "document_expiry",
        "discrepancy",
        "suspicious_activity",
        "other_risk_event",
    }
)
_REVERIFICATION_SEVERITIES = frozenset({"standard", "elevated", "critical"})


class CifRepositoryError(RuntimeError):
    code = "cif_repository_error"


class CifNotFound(CifRepositoryError):
    code = "cif_not_found"


class CifClientNotFound(CifRepositoryError):
    code = "cif_client_not_found"


class CifConflict(CifRepositoryError):
    code = "cif_conflict"


class CifInvalidTransition(CifRepositoryError):
    code = "cif_invalid_transition"


class CifStaleRevision(CifRepositoryError):
    code = "cif_stale_revision"


class CifValidationError(ValueError):
    code = "cif_validation_error"


@dataclass(frozen=True, slots=True)
class CifDraftInput:
    legal_full_name: str
    birth_date: date | None = None
    nationality: str | None = None
    civil_status: str | None = None
    phone_number: str | None = None
    email: str | None = None
    present_address: Mapping[str, object] | None = None
    permanent_address: Mapping[str, object] | None = None
    livelihood_profile: Mapping[str, object] | None = None
    privacy_notice_version: str = "cif-v1"
    privacy_acknowledged_at: datetime | None = None
    client_signature_reference: str | None = None
    client_signature_sha256: str | None = None
    form_schema_version: str = "cif-v1"


@dataclass(frozen=True, slots=True)
class CifRecord:
    cif_id: UUID
    cif_number: str
    client_id: UUID
    form_version: int
    durable_state: CifDurableState
    public_status: str
    is_eligible_for_new_credit: bool
    reverification_required: bool
    allows_existing_obligation_servicing: bool
    effective_at: datetime | None
    expires_at: datetime | None
    supersedes_cif_id: UUID | None
    legal_full_name: str
    birth_date: date | None
    nationality: str | None
    civil_status: str | None
    phone_number: str | None
    email: str | None
    present_address: dict[str, object]
    permanent_address: dict[str, object]
    livelihood_profile: dict[str, object]
    privacy_notice_version: str
    privacy_acknowledged_at: datetime | None
    client_signature_reference: str | None
    client_signature_sha256: str | None
    prepared_by_user_id: UUID
    verified_by_user_id: UUID | None
    verified_at: datetime | None
    approved_by_user_id: UUID | None
    approved_at: datetime | None
    content_digest_sha256: str | None
    form_schema_version: str
    draft_revision: int
    created_at: datetime
    updated_at: datetime


def _clean_required(value: str, *, field: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise CifValidationError(f"{field} is required")
    return normalized


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split())
    return normalized or None


def _normalize_mapping(
    value: Mapping[str, object] | None,
    *,
    allowed: frozenset[str],
    label: str,
) -> dict[str, object]:
    if value is None:
        return {}
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise CifValidationError(
            f"unsupported {label} field: {', '.join(unknown)}"
        )
    normalized: dict[str, object] = {}
    for key in sorted(value):
        item = value[key]
        if item is None:
            continue
        if isinstance(item, str):
            clean = " ".join(item.split())
            if clean:
                normalized[key] = clean
            continue
        if isinstance(item, (bool, int, float)):
            normalized[key] = item
            continue
        raise CifValidationError(f"unsupported {label} value for {key}")
    return normalized


def validate_cif_draft(
    draft: CifDraftInput,
    *,
    require_complete: bool = False,
) -> CifDraftInput:
    legal_full_name = _clean_required(draft.legal_full_name, field="legal full name")
    privacy_notice_version = _clean_required(
        draft.privacy_notice_version,
        field="privacy notice version",
    )
    form_schema_version = _clean_required(
        draft.form_schema_version,
        field="form schema version",
    )
    email = _clean_optional(draft.email)
    if email is not None:
        email = email.lower()
    present_address = _normalize_mapping(
        draft.present_address,
        allowed=_ADDRESS_FIELDS,
        label="address",
    )
    permanent_address = _normalize_mapping(
        draft.permanent_address,
        allowed=_ADDRESS_FIELDS,
        label="address",
    )
    livelihood_profile = _normalize_mapping(
        draft.livelihood_profile,
        allowed=_LIVELIHOOD_FIELDS,
        label="livelihood",
    )
    signature_reference = _clean_optional(draft.client_signature_reference)
    signature_digest = _clean_optional(draft.client_signature_sha256)
    if signature_digest is not None and not _SHA256_RE.fullmatch(signature_digest):
        raise CifValidationError("client signature digest must be lowercase SHA-256")

    if draft.privacy_acknowledged_at is not None:
        if (
            draft.privacy_acknowledged_at.tzinfo is None
            or draft.privacy_acknowledged_at.utcoffset() is None
        ):
            raise CifValidationError("privacy acknowledgment must be timezone-aware")

    if require_complete:
        if not present_address:
            raise CifValidationError("present address is required before verification")
        if draft.privacy_acknowledged_at is None:
            raise CifValidationError(
                "privacy acknowledgment is required before verification"
            )
        if signature_reference is None:
            raise CifValidationError(
                "client signature reference is required before verification"
            )
        if signature_digest is None:
            raise CifValidationError(
                "client signature SHA-256 is required before verification"
            )

    return CifDraftInput(
        legal_full_name=legal_full_name,
        birth_date=draft.birth_date,
        nationality=_clean_optional(draft.nationality),
        civil_status=_clean_optional(draft.civil_status),
        phone_number=_clean_optional(draft.phone_number),
        email=email,
        present_address=present_address,
        permanent_address=permanent_address,
        livelihood_profile=livelihood_profile,
        privacy_notice_version=privacy_notice_version,
        privacy_acknowledged_at=draft.privacy_acknowledged_at,
        client_signature_reference=signature_reference,
        client_signature_sha256=signature_digest,
        form_schema_version=form_schema_version,
    )


def _json_value(value: object) -> object:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {key: _json_value(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def canonical_cif_digest(draft: CifDraftInput) -> str:
    normalized = validate_cif_draft(draft)
    payload = {
        key: _json_value(value)
        for key, value in asdict(normalized).items()
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _default_connection_factory() -> Any:
    settings = get_settings()
    return psycopg.connect(
        normalize_database_url_for_psycopg(settings.database_url),
        row_factory=dict_row,
    )


def _as_mapping(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _draft_from_row(row: Mapping[str, object]) -> CifDraftInput:
    return CifDraftInput(
        legal_full_name=str(row["legal_full_name"]),
        birth_date=row.get("birth_date") if isinstance(row.get("birth_date"), date) else None,
        nationality=row.get("nationality") if isinstance(row.get("nationality"), str) else None,
        civil_status=row.get("civil_status") if isinstance(row.get("civil_status"), str) else None,
        phone_number=row.get("phone_number") if isinstance(row.get("phone_number"), str) else None,
        email=row.get("email") if isinstance(row.get("email"), str) else None,
        present_address=_as_mapping(row.get("present_address")),
        permanent_address=_as_mapping(row.get("permanent_address")),
        livelihood_profile=_as_mapping(row.get("livelihood_profile")),
        privacy_notice_version=str(row["privacy_notice_version"]),
        privacy_acknowledged_at=(
            row.get("privacy_acknowledged_at")
            if isinstance(row.get("privacy_acknowledged_at"), datetime)
            else None
        ),
        client_signature_reference=(
            row.get("client_signature_reference")
            if isinstance(row.get("client_signature_reference"), str)
            else None
        ),
        client_signature_sha256=(
            row.get("client_signature_sha256")
            if isinstance(row.get("client_signature_sha256"), str)
            else None
        ),
        form_schema_version=str(row["form_schema_version"]),
    )


def _evaluation_from_row(row: Mapping[str, object]) -> CifEvaluation:
    state = CifDurableState(str(row["lifecycle_state"]))
    effective_at = row.get("effective_at")
    expires_at = row.get("expires_at")
    now = datetime.now(UTC)
    return evaluate_cif(
        durable_state=state,
        effective_at=effective_at if isinstance(effective_at, datetime) else None,
        expires_at=expires_at if isinstance(expires_at, datetime) else None,
        now=now,
        has_open_reverification=bool(row.get("reverification_required", False)),
    )


def _record_from_row(row: Mapping[str, object]) -> CifRecord:
    evaluation = _evaluation_from_row(row)
    return CifRecord(
        cif_id=UUID(str(row["id"])),
        cif_number=str(row["cif_number"]),
        client_id=UUID(str(row["client_id"])),
        form_version=int(row["form_version"]),
        durable_state=CifDurableState(str(row["lifecycle_state"])),
        public_status=evaluation.public_status.value,
        is_eligible_for_new_credit=evaluation.is_eligible_for_new_credit,
        reverification_required=evaluation.reverification_required,
        allows_existing_obligation_servicing=True,
        effective_at=evaluation.effective_at,
        expires_at=evaluation.expires_at,
        supersedes_cif_id=(
            UUID(str(row["supersedes_cif_id"]))
            if row.get("supersedes_cif_id") is not None
            else None
        ),
        legal_full_name=str(row["legal_full_name"]),
        birth_date=row.get("birth_date") if isinstance(row.get("birth_date"), date) else None,
        nationality=row.get("nationality") if isinstance(row.get("nationality"), str) else None,
        civil_status=row.get("civil_status") if isinstance(row.get("civil_status"), str) else None,
        phone_number=row.get("phone_number") if isinstance(row.get("phone_number"), str) else None,
        email=row.get("email") if isinstance(row.get("email"), str) else None,
        present_address=_as_mapping(row.get("present_address")),
        permanent_address=_as_mapping(row.get("permanent_address")),
        livelihood_profile=_as_mapping(row.get("livelihood_profile")),
        privacy_notice_version=str(row["privacy_notice_version"]),
        privacy_acknowledged_at=(
            row.get("privacy_acknowledged_at")
            if isinstance(row.get("privacy_acknowledged_at"), datetime)
            else None
        ),
        client_signature_reference=(
            row.get("client_signature_reference")
            if isinstance(row.get("client_signature_reference"), str)
            else None
        ),
        client_signature_sha256=(
            row.get("client_signature_sha256")
            if isinstance(row.get("client_signature_sha256"), str)
            else None
        ),
        prepared_by_user_id=UUID(str(row["prepared_by_user_id"])),
        verified_by_user_id=(
            UUID(str(row["verified_by_user_id"]))
            if row.get("verified_by_user_id") is not None
            else None
        ),
        verified_at=(
            row.get("verified_at") if isinstance(row.get("verified_at"), datetime) else None
        ),
        approved_by_user_id=(
            UUID(str(row["approved_by_user_id"]))
            if row.get("approved_by_user_id") is not None
            else None
        ),
        approved_at=(
            row.get("approved_at") if isinstance(row.get("approved_at"), datetime) else None
        ),
        content_digest_sha256=(
            str(row["content_digest_sha256"])
            if row.get("content_digest_sha256") is not None
            else None
        ),
        form_schema_version=str(row["form_schema_version"]),
        draft_revision=int(row["draft_revision"]),
        created_at=row["created_at"] if isinstance(row["created_at"], datetime) else now,
        updated_at=row["updated_at"] if isinstance(row["updated_at"], datetime) else now,
    )


_CIF_SELECT = """
    select
        form.*,
        exists (
            select 1
            from lending.client_cif_reverification_requirements requirement
            where requirement.client_id = form.client_id
              and requirement.status = 'open'
        ) as reverification_required
    from lending.client_information_forms form
"""


class PostgresCifRepository:
    def __init__(self, connection_factory: Callable[[], Any] | None = None) -> None:
        self._connection_factory = connection_factory or _default_connection_factory

    def list_for_client(self, *, client_id: UUID) -> tuple[CifRecord, ...]:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    _CIF_SELECT
                    + " where form.client_id = %s order by form.form_version desc",
                    (client_id,),
                )
                return tuple(_record_from_row(row) for row in cursor.fetchall())

    def get(self, *, cif_id: UUID) -> CifRecord:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(_CIF_SELECT + " where form.id = %s", (cif_id,))
                row = cursor.fetchone()
                if row is None:
                    raise CifNotFound("Client Information Form was not found")
                return _record_from_row(row)

    def create_draft(
        self,
        *,
        client_id: UUID,
        actor_user_id: UUID,
        draft: CifDraftInput,
    ) -> CifRecord:
        normalized = validate_cif_draft(draft)
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "select id from lending.clients where id = %s for update",
                    (client_id,),
                )
                if cursor.fetchone() is None:
                    raise CifClientNotFound("Client was not found")
                cursor.execute(
                    """
                    select coalesce(max(form_version), 0) + 1 as next_version
                    from lending.client_information_forms
                    where client_id = %s
                    """,
                    (client_id,),
                )
                version_row = cursor.fetchone()
                next_version = int(version_row["next_version"])
                cursor.execute(
                    "select nextval('lending.client_cif_number_sequence') as value"
                )
                sequence_value = int(cursor.fetchone()["value"])
                cif_number = f"CIF-{sequence_value:010d}"
                cursor.execute(
                    """
                    insert into lending.client_information_forms (
                        cif_number,
                        client_id,
                        form_version,
                        legal_full_name,
                        birth_date,
                        nationality,
                        civil_status,
                        phone_number,
                        email,
                        present_address,
                        permanent_address,
                        livelihood_profile,
                        privacy_notice_version,
                        privacy_acknowledged_at,
                        client_signature_reference,
                        client_signature_sha256,
                        prepared_by_user_id,
                        form_schema_version
                    ) values (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s::jsonb, %s::jsonb, %s::jsonb,
                        %s, %s, %s, %s, %s, %s
                    )
                    returning id
                    """,
                    (
                        cif_number,
                        client_id,
                        next_version,
                        normalized.legal_full_name,
                        normalized.birth_date,
                        normalized.nationality,
                        normalized.civil_status,
                        normalized.phone_number,
                        normalized.email,
                        json.dumps(normalized.present_address),
                        json.dumps(normalized.permanent_address),
                        json.dumps(normalized.livelihood_profile),
                        normalized.privacy_notice_version,
                        normalized.privacy_acknowledged_at,
                        normalized.client_signature_reference,
                        normalized.client_signature_sha256,
                        actor_user_id,
                        normalized.form_schema_version,
                    ),
                )
                cif_id = UUID(str(cursor.fetchone()["id"]))
                self._insert_event(
                    cursor,
                    cif_id=cif_id,
                    client_id=client_id,
                    actor_user_id=actor_user_id,
                    event_type="created",
                    details={"form_version": next_version},
                )
        return self.get(cif_id=cif_id)

    def update_draft(
        self,
        *,
        cif_id: UUID,
        actor_user_id: UUID,
        expected_revision: int,
        draft: CifDraftInput,
    ) -> CifRecord:
        normalized = validate_cif_draft(draft)
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                row = self._select_locked(cursor, cif_id=cif_id)
                if str(row["lifecycle_state"]) != "draft":
                    raise CifInvalidTransition("Only a draft CIF can be edited")
                if int(row["draft_revision"]) != expected_revision:
                    raise CifStaleRevision("CIF draft revision is stale")
                cursor.execute(
                    """
                    update lending.client_information_forms
                    set legal_full_name = %s,
                        birth_date = %s,
                        nationality = %s,
                        civil_status = %s,
                        phone_number = %s,
                        email = %s,
                        present_address = %s::jsonb,
                        permanent_address = %s::jsonb,
                        livelihood_profile = %s::jsonb,
                        privacy_notice_version = %s,
                        privacy_acknowledged_at = %s,
                        client_signature_reference = %s,
                        client_signature_sha256 = %s,
                        form_schema_version = %s,
                        verified_by_user_id = null,
                        verified_at = null,
                        approved_by_user_id = null,
                        approved_at = null,
                        content_digest_sha256 = null,
                        effective_at = null,
                        expires_at = null,
                        draft_revision = draft_revision + 1,
                        updated_at = now()
                    where id = %s and draft_revision = %s
                    """,
                    (
                        normalized.legal_full_name,
                        normalized.birth_date,
                        normalized.nationality,
                        normalized.civil_status,
                        normalized.phone_number,
                        normalized.email,
                        json.dumps(normalized.present_address),
                        json.dumps(normalized.permanent_address),
                        json.dumps(normalized.livelihood_profile),
                        normalized.privacy_notice_version,
                        normalized.privacy_acknowledged_at,
                        normalized.client_signature_reference,
                        normalized.client_signature_sha256,
                        normalized.form_schema_version,
                        cif_id,
                        expected_revision,
                    ),
                )
                if cursor.rowcount != 1:
                    raise CifStaleRevision("CIF draft revision is stale")
                self._insert_event(
                    cursor,
                    cif_id=cif_id,
                    client_id=UUID(str(row["client_id"])),
                    actor_user_id=actor_user_id,
                    event_type="draft_updated",
                    details={"previous_revision": expected_revision},
                )
        return self.get(cif_id=cif_id)

    def verify(
        self,
        *,
        cif_id: UUID,
        actor_user_id: UUID,
        expected_revision: int,
    ) -> CifRecord:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                row = self._select_locked(cursor, cif_id=cif_id)
                if str(row["lifecycle_state"]) != "draft":
                    raise CifInvalidTransition("Only a draft CIF can be verified")
                if int(row["draft_revision"]) != expected_revision:
                    raise CifStaleRevision("CIF draft revision is stale")
                normalized = validate_cif_draft(
                    _draft_from_row(row),
                    require_complete=True,
                )
                digest = canonical_cif_digest(normalized)
                cursor.execute(
                    """
                    update lending.client_information_forms
                    set verified_by_user_id = %s,
                        verified_at = now(),
                        approved_by_user_id = null,
                        approved_at = null,
                        content_digest_sha256 = %s,
                        updated_at = now()
                    where id = %s and draft_revision = %s
                    """,
                    (actor_user_id, digest, cif_id, expected_revision),
                )
                if cursor.rowcount != 1:
                    raise CifStaleRevision("CIF draft revision is stale")
                self._insert_event(
                    cursor,
                    cif_id=cif_id,
                    client_id=UUID(str(row["client_id"])),
                    actor_user_id=actor_user_id,
                    event_type="verified",
                    details={"content_digest_sha256": digest},
                )
        return self.get(cif_id=cif_id)

    def activate(
        self,
        *,
        cif_id: UUID,
        actor_user_id: UUID,
        expected_revision: int,
    ) -> CifRecord:
        effective_at = datetime.now(UTC)
        expires_at = add_five_years(effective_at)
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                row = self._select_locked(cursor, cif_id=cif_id)
                if str(row["lifecycle_state"]) != "draft":
                    raise CifInvalidTransition("Only a draft CIF can be activated")
                if int(row["draft_revision"]) != expected_revision:
                    raise CifStaleRevision("CIF draft revision is stale")
                verified_by = row.get("verified_by_user_id")
                verified_at = row.get("verified_at")
                stored_digest = row.get("content_digest_sha256")
                if verified_by is None or verified_at is None or stored_digest is None:
                    raise CifInvalidTransition("CIF must be verified before activation")
                if UUID(str(verified_by)) == actor_user_id:
                    raise CifConflict("CIF verifier and approver must be different users")
                current_digest = canonical_cif_digest(
                    validate_cif_draft(_draft_from_row(row), require_complete=True)
                )
                if current_digest != str(stored_digest):
                    raise CifConflict("Verified CIF content changed before activation")

                client_id = UUID(str(row["client_id"]))
                cursor.execute(
                    "select id from lending.clients where id = %s for update",
                    (client_id,),
                )
                if cursor.fetchone() is None:
                    raise CifClientNotFound("Client was not found")
                cursor.execute(
                    """
                    select id
                    from lending.client_information_forms
                    where client_id = %s
                      and lifecycle_state = 'active'
                      and id <> %s
                    for update
                    """,
                    (client_id, cif_id),
                )
                previous_active = cursor.fetchone()
                previous_active_id: UUID | None = None
                if previous_active is not None:
                    previous_active_id = UUID(str(previous_active["id"]))
                    cursor.execute(
                        """
                        update lending.client_information_forms
                        set lifecycle_state = 'superseded', updated_at = now()
                        where id = %s and lifecycle_state = 'active'
                        """,
                        (previous_active_id,),
                    )
                    if cursor.rowcount != 1:
                        raise CifConflict("Active CIF changed during activation")
                    self._insert_event(
                        cursor,
                        cif_id=previous_active_id,
                        client_id=client_id,
                        actor_user_id=actor_user_id,
                        event_type="superseded",
                        details={"superseded_by_cif_id": str(cif_id)},
                    )

                cursor.execute(
                    """
                    update lending.client_information_forms
                    set lifecycle_state = 'active',
                        effective_at = %s,
                        expires_at = %s,
                        supersedes_cif_id = %s,
                        approved_by_user_id = %s,
                        approved_at = %s,
                        updated_at = %s
                    where id = %s
                      and lifecycle_state = 'draft'
                      and draft_revision = %s
                      and content_digest_sha256 = %s
                    """,
                    (
                        effective_at,
                        expires_at,
                        previous_active_id,
                        actor_user_id,
                        effective_at,
                        effective_at,
                        cif_id,
                        expected_revision,
                        stored_digest,
                    ),
                )
                if cursor.rowcount != 1:
                    raise CifConflict("CIF changed during activation")

                cursor.execute(
                    """
                    update lending.client_cif_reverification_requirements
                    set status = 'resolved',
                        resolution_cif_id = %s,
                        resolved_by_user_id = %s,
                        resolved_at = %s
                    where client_id = %s and status = 'open'
                    """,
                    (cif_id, actor_user_id, effective_at, client_id),
                )
                self._insert_event(
                    cursor,
                    cif_id=cif_id,
                    client_id=client_id,
                    actor_user_id=actor_user_id,
                    event_type="activated",
                    details={
                        "effective_at": effective_at.isoformat(),
                        "expires_at": expires_at.isoformat(),
                        "supersedes_cif_id": (
                            str(previous_active_id) if previous_active_id else None
                        ),
                    },
                )
        return self.get(cif_id=cif_id)

    def open_reverification(
        self,
        *,
        client_id: UUID,
        actor_user_id: UUID,
        reason: str,
        severity: str,
        note: str,
    ) -> UUID:
        normalized_reason = reason.strip().lower()
        normalized_severity = severity.strip().lower()
        if normalized_reason not in _REVERIFICATION_REASONS:
            raise CifValidationError("unsupported CIF re-verification reason")
        if normalized_severity not in _REVERIFICATION_SEVERITIES:
            raise CifValidationError("unsupported CIF re-verification severity")
        normalized_note = " ".join(note.split())
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "select id from lending.clients where id = %s for update",
                    (client_id,),
                )
                if cursor.fetchone() is None:
                    raise CifClientNotFound("Client was not found")
                cursor.execute(
                    """
                    select id
                    from lending.client_information_forms
                    where client_id = %s and lifecycle_state = 'active'
                    for update
                    """,
                    (client_id,),
                )
                active = cursor.fetchone()
                if active is None:
                    raise CifInvalidTransition(
                        "An active CIF is required to open re-verification"
                    )
                source_cif_id = UUID(str(active["id"]))
                cursor.execute(
                    """
                    insert into lending.client_cif_reverification_requirements (
                        client_id,
                        source_cif_id,
                        reason,
                        severity,
                        note,
                        opened_by_user_id
                    ) values (%s, %s, %s, %s, %s, %s)
                    returning id
                    """,
                    (
                        client_id,
                        source_cif_id,
                        normalized_reason,
                        normalized_severity,
                        normalized_note,
                        actor_user_id,
                    ),
                )
                requirement_id = UUID(str(cursor.fetchone()["id"]))
                self._insert_event(
                    cursor,
                    cif_id=source_cif_id,
                    client_id=client_id,
                    actor_user_id=actor_user_id,
                    event_type="reverification_opened",
                    details={
                        "requirement_id": str(requirement_id),
                        "reason": normalized_reason,
                        "severity": normalized_severity,
                    },
                )
                return requirement_id

    @staticmethod
    def _select_locked(cursor: Any, *, cif_id: UUID) -> Mapping[str, object]:
        cursor.execute(
            """
            select *
            from lending.client_information_forms
            where id = %s
            for update
            """,
            (cif_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise CifNotFound("Client Information Form was not found")
        return row

    @staticmethod
    def _insert_event(
        cursor: Any,
        *,
        cif_id: UUID,
        client_id: UUID,
        actor_user_id: UUID,
        event_type: str,
        details: Mapping[str, object],
    ) -> None:
        cursor.execute(
            """
            insert into lending.client_cif_events (
                cif_id,
                client_id,
                event_type,
                actor_user_id,
                details
            ) values (%s, %s, %s, %s, %s::jsonb)
            """,
            (
                cif_id,
                client_id,
                event_type,
                actor_user_id,
                json.dumps(details, sort_keys=True),
            ),
        )
