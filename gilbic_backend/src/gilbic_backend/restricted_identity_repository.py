from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .config import get_settings
from .database import normalize_database_url_for_psycopg


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_LONG_NUMBER_RE = re.compile(r"(?:\d[\s-]*){8,}")
_EVIDENCE_TYPES = frozenset(
    {
        "national_id_check",
        "everify_outcome",
        "government_id_metadata",
        "utility_proof",
        "residence_visit",
        "approved_exception",
    }
)
_RESULTS = frozenset(
    {"verified", "not_verified", "inconclusive", "exception_approved"}
)
_RETENTION_CLASSES = frozenset(
    {
        "identity_verification",
        "residence_verification",
        "exception_evidence",
    }
)
_PURPOSE_CODES = frozenset(
    {
        "initial_cif_verification",
        "reverification",
        "discrepancy_review",
        "compliance_review",
        "legal_hold",
        "retention_disposal",
    }
)
_ACTIONS = frozenset({"list", "view", "create", "review", "supersede"})


class RestrictedIdentityRepositoryError(RuntimeError):
    code = "restricted_identity_repository_error"


class RestrictedEvidenceNotFound(RestrictedIdentityRepositoryError):
    code = "restricted_evidence_not_found"


class RestrictedEvidenceConflict(RestrictedIdentityRepositoryError):
    code = "restricted_evidence_conflict"


class RestrictedEvidenceValidationError(ValueError):
    code = "restricted_evidence_validation_error"


@dataclass(frozen=True, slots=True)
class RestrictedEvidenceInput:
    evidence_type: str
    verification_method: str
    verification_result: str
    checked_at: datetime
    document_date: date | None
    document_expires_at: datetime | None
    masked_reference: str | None
    external_evidence_reference: str | None
    evidence_sha256: str
    retention_class: str
    retain_until: date
    legal_hold: bool = False
    requires_separate_reviewer: bool = False


@dataclass(frozen=True, slots=True)
class RestrictedEvidenceRecord:
    evidence_id: UUID
    cif_id: UUID
    client_id: UUID
    evidence_type: str
    verification_method: str
    verification_result: str
    checked_at: datetime
    document_date: date | None
    document_expires_at: datetime | None
    masked_reference: str | None
    external_evidence_reference: str | None
    evidence_sha256: str
    retention_class: str
    retain_until: date
    legal_hold: bool
    review_state: str
    verified_by_user_id: UUID
    final_reviewed_by_user_id: UUID | None
    reviewed_at: datetime | None
    supersedes_evidence_id: UUID | None
    created_by_user_id: UUID
    created_at: datetime


def _clean_required(value: str, *, field: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise RestrictedEvidenceValidationError(f"{field} is required")
    return normalized


def _clean_optional_reference(
    value: str | None,
    *,
    field: str,
) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise RestrictedEvidenceValidationError(
            f"{field} must be a text reference, not raw evidence"
        )
    normalized = " ".join(value.split())
    return normalized or None


def normalize_masked_reference(value: str | None) -> str | None:
    normalized = _clean_optional_reference(
        value,
        field="masked reference",
    )
    if normalized is None:
        return None
    if _LONG_NUMBER_RE.search(normalized) and not any(
        mask in normalized for mask in ("*", "•", "x", "X")
    ):
        raise RestrictedEvidenceValidationError(
            "identifier reference must be masked"
        )
    if len(normalized) > 120:
        raise RestrictedEvidenceValidationError(
            "masked reference exceeds the allowed length"
        )
    return normalized


def validate_purpose_code(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in _PURPOSE_CODES:
        raise RestrictedEvidenceValidationError(
            "unsupported restricted-evidence purpose"
        )
    return normalized


def validate_restricted_evidence(
    evidence: RestrictedEvidenceInput,
) -> RestrictedEvidenceInput:
    evidence_type = evidence.evidence_type.strip().lower()
    if evidence_type not in _EVIDENCE_TYPES:
        raise RestrictedEvidenceValidationError(
            "unsupported restricted evidence type"
        )
    result = evidence.verification_result.strip().lower()
    if result not in _RESULTS:
        raise RestrictedEvidenceValidationError(
            "unsupported restricted evidence result"
        )
    retention_class = evidence.retention_class.strip().lower()
    if retention_class not in _RETENTION_CLASSES:
        raise RestrictedEvidenceValidationError(
            "unsupported restricted evidence retention class"
        )
    if (
        evidence.checked_at.tzinfo is None
        or evidence.checked_at.utcoffset() is None
    ):
        raise RestrictedEvidenceValidationError(
            "evidence check timestamp must be timezone-aware"
        )
    expires_at = evidence.document_expires_at
    if expires_at is not None and (
        expires_at.tzinfo is None or expires_at.utcoffset() is None
    ):
        raise RestrictedEvidenceValidationError(
            "document expiry timestamp must be timezone-aware"
        )
    digest = evidence.evidence_sha256.strip()
    if not _SHA256_RE.fullmatch(digest):
        raise RestrictedEvidenceValidationError(
            "evidence digest must be lowercase SHA-256"
        )
    if evidence.retain_until < evidence.checked_at.date():
        raise RestrictedEvidenceValidationError(
            "retention date cannot precede the evidence check date"
        )
    external_reference = _clean_optional_reference(
        evidence.external_evidence_reference,
        field="external evidence reference",
    )
    if external_reference is None:
        raise RestrictedEvidenceValidationError(
            "external evidence reference is required"
        )
    if len(external_reference) > 500:
        raise RestrictedEvidenceValidationError(
            "external evidence reference exceeds the allowed length"
        )
    if evidence_type == "approved_exception" and result != "exception_approved":
        raise RestrictedEvidenceValidationError(
            "approved exception evidence requires exception_approved result"
        )
    if result == "exception_approved" and evidence_type != "approved_exception":
        raise RestrictedEvidenceValidationError(
            "exception_approved result is limited to approved exception evidence"
        )

    return RestrictedEvidenceInput(
        evidence_type=evidence_type,
        verification_method=_clean_required(
            evidence.verification_method,
            field="verification method",
        ),
        verification_result=result,
        checked_at=evidence.checked_at,
        document_date=evidence.document_date,
        document_expires_at=expires_at,
        masked_reference=normalize_masked_reference(
            evidence.masked_reference
        ),
        external_evidence_reference=external_reference,
        evidence_sha256=digest,
        retention_class=retention_class,
        retain_until=evidence.retain_until,
        legal_hold=bool(evidence.legal_hold),
        requires_separate_reviewer=(evidence_type == "approved_exception"),
    )


def _default_connection_factory() -> Any:
    settings = get_settings()
    return psycopg.connect(
        normalize_database_url_for_psycopg(settings.database_url),
        row_factory=dict_row,
    )


def _optional_uuid(row: Mapping[str, object], key: str) -> UUID | None:
    value = row.get(key)
    return UUID(str(value)) if value is not None else None


def _optional_text(row: Mapping[str, object], key: str) -> str | None:
    value = row.get(key)
    return value if isinstance(value, str) else None


def _record_from_row(row: Mapping[str, object]) -> RestrictedEvidenceRecord:
    checked_at = row["checked_at"]
    created_at = row["created_at"]
    retain_until = row["retain_until"]
    if not isinstance(checked_at, datetime):
        raise RestrictedIdentityRepositoryError(
            "Stored evidence check time is invalid"
        )
    if not isinstance(created_at, datetime):
        raise RestrictedIdentityRepositoryError(
            "Stored evidence creation time is invalid"
        )
    if not isinstance(retain_until, date):
        raise RestrictedIdentityRepositoryError(
            "Stored evidence retention date is invalid"
        )
    document_date_value = row.get("document_date")
    document_expiry_value = row.get("document_expires_at")
    reviewed_at_value = row.get("reviewed_at")
    return RestrictedEvidenceRecord(
        evidence_id=UUID(str(row["id"])),
        cif_id=UUID(str(row["cif_id"])),
        client_id=UUID(str(row["client_id"])),
        evidence_type=str(row["evidence_type"]),
        verification_method=str(row["verification_method"]),
        verification_result=str(row["verification_result"]),
        checked_at=checked_at,
        document_date=(
            document_date_value
            if isinstance(document_date_value, date)
            else None
        ),
        document_expires_at=(
            document_expiry_value
            if isinstance(document_expiry_value, datetime)
            else None
        ),
        masked_reference=_optional_text(row, "masked_reference"),
        external_evidence_reference=_optional_text(
            row,
            "external_evidence_reference",
        ),
        evidence_sha256=str(row["evidence_sha256"]),
        retention_class=str(row["retention_class"]),
        retain_until=retain_until,
        legal_hold=bool(row["legal_hold"]),
        review_state=str(row["review_state"]),
        verified_by_user_id=UUID(str(row["verified_by_user_id"])),
        final_reviewed_by_user_id=_optional_uuid(
            row,
            "final_reviewed_by_user_id",
        ),
        reviewed_at=(
            reviewed_at_value
            if isinstance(reviewed_at_value, datetime)
            else None
        ),
        supersedes_evidence_id=_optional_uuid(
            row,
            "supersedes_evidence_id",
        ),
        created_by_user_id=UUID(str(row["created_by_user_id"])),
        created_at=created_at,
    )


class PostgresRestrictedIdentityRepository:
    def __init__(
        self,
        connection_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._connection_factory = (
            connection_factory or _default_connection_factory
        )

    def list_for_cif(
        self,
        *,
        cif_id: UUID,
        actor_user_id: UUID,
        registered_device_id: UUID,
        purpose_code: str,
        request_id: UUID,
    ) -> tuple[RestrictedEvidenceRecord, ...]:
        purpose = validate_purpose_code(purpose_code)
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                client_id = self._client_for_cif(
                    cursor,
                    cif_id=cif_id,
                )
                cursor.execute(
                    """
                    select *
                    from restricted_identity.cif_verification_evidence
                    where cif_id = %s
                    order by created_at desc, id
                    """,
                    (cif_id,),
                )
                rows = cursor.fetchall()
                self._insert_access_event(
                    cursor,
                    evidence_id=None,
                    cif_id=cif_id,
                    client_id=client_id,
                    actor_user_id=actor_user_id,
                    registered_device_id=registered_device_id,
                    action="list",
                    purpose_code=purpose,
                    request_id=request_id,
                )
                return tuple(_record_from_row(row) for row in rows)

    def get(
        self,
        *,
        evidence_id: UUID,
        actor_user_id: UUID,
        registered_device_id: UUID,
        purpose_code: str,
        request_id: UUID,
    ) -> RestrictedEvidenceRecord:
        purpose = validate_purpose_code(purpose_code)
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                row = self._select_locked(
                    cursor,
                    evidence_id=evidence_id,
                    for_update=False,
                )
                self._insert_access_event(
                    cursor,
                    evidence_id=evidence_id,
                    cif_id=UUID(str(row["cif_id"])),
                    client_id=UUID(str(row["client_id"])),
                    actor_user_id=actor_user_id,
                    registered_device_id=registered_device_id,
                    action="view",
                    purpose_code=purpose,
                    request_id=request_id,
                )
                return _record_from_row(row)

    def create(
        self,
        *,
        cif_id: UUID,
        actor_user_id: UUID,
        registered_device_id: UUID,
        purpose_code: str,
        request_id: UUID,
        evidence: RestrictedEvidenceInput,
    ) -> RestrictedEvidenceRecord:
        normalized = validate_restricted_evidence(evidence)
        purpose = validate_purpose_code(purpose_code)
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                client_id = self._client_for_cif(
                    cursor,
                    cif_id=cif_id,
                )
                cursor.execute(
                    """
                    insert into restricted_identity.cif_verification_evidence (
                        cif_id, client_id, evidence_type,
                        verification_method, verification_result,
                        checked_at, document_date, document_expires_at,
                        masked_reference, external_evidence_reference,
                        evidence_sha256, retention_class, retain_until,
                        legal_hold, verified_by_user_id,
                        created_by_user_id
                    ) values (
                        %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    returning *
                    """,
                    (
                        cif_id,
                        client_id,
                        normalized.evidence_type,
                        normalized.verification_method,
                        normalized.verification_result,
                        normalized.checked_at,
                        normalized.document_date,
                        normalized.document_expires_at,
                        normalized.masked_reference,
                        normalized.external_evidence_reference,
                        normalized.evidence_sha256,
                        normalized.retention_class,
                        normalized.retain_until,
                        normalized.legal_hold,
                        actor_user_id,
                        actor_user_id,
                    ),
                )
                row = cursor.fetchone()
                evidence_id = UUID(str(row["id"]))
                self._insert_access_event(
                    cursor,
                    evidence_id=evidence_id,
                    cif_id=cif_id,
                    client_id=client_id,
                    actor_user_id=actor_user_id,
                    registered_device_id=registered_device_id,
                    action="create",
                    purpose_code=purpose,
                    request_id=request_id,
                )
                return _record_from_row(row)

    def review(
        self,
        *,
        evidence_id: UUID,
        actor_user_id: UUID,
        registered_device_id: UUID,
        purpose_code: str,
        request_id: UUID,
        decision: str,
    ) -> RestrictedEvidenceRecord:
        purpose = validate_purpose_code(purpose_code)
        normalized_decision = decision.strip().lower()
        if normalized_decision not in {"verified", "rejected"}:
            raise RestrictedEvidenceValidationError(
                "unsupported restricted evidence review decision"
            )
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                row = self._select_locked(
                    cursor,
                    evidence_id=evidence_id,
                    for_update=True,
                )
                if str(row["review_state"]) != "draft":
                    raise RestrictedEvidenceConflict(
                        "Only draft evidence can be reviewed"
                    )
                if (
                    str(row["evidence_type"]) == "approved_exception"
                    and UUID(str(row["verified_by_user_id"]))
                    == actor_user_id
                ):
                    raise RestrictedEvidenceConflict(
                        "Exception verifier and final reviewer must differ"
                    )
                cursor.execute(
                    """
                    update restricted_identity.cif_verification_evidence
                    set review_state = %s,
                        final_reviewed_by_user_id = %s,
                        reviewed_at = now()
                    where id = %s and review_state = 'draft'
                    returning *
                    """,
                    (
                        normalized_decision,
                        actor_user_id,
                        evidence_id,
                    ),
                )
                updated = cursor.fetchone()
                if updated is None:
                    raise RestrictedEvidenceConflict(
                        "Evidence changed during review"
                    )
                self._insert_access_event(
                    cursor,
                    evidence_id=evidence_id,
                    cif_id=UUID(str(row["cif_id"])),
                    client_id=UUID(str(row["client_id"])),
                    actor_user_id=actor_user_id,
                    registered_device_id=registered_device_id,
                    action="review",
                    purpose_code=purpose,
                    request_id=request_id,
                )
                return _record_from_row(updated)

    def supersede(
        self,
        *,
        evidence_id: UUID,
        replacement: RestrictedEvidenceInput,
        actor_user_id: UUID,
        registered_device_id: UUID,
        purpose_code: str,
        request_id: UUID,
    ) -> RestrictedEvidenceRecord:
        normalized = validate_restricted_evidence(replacement)
        purpose = validate_purpose_code(purpose_code)
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                current = self._select_locked(
                    cursor,
                    evidence_id=evidence_id,
                    for_update=True,
                )
                if str(current["review_state"]) != "verified":
                    raise RestrictedEvidenceConflict(
                        "Only verified evidence can be superseded"
                    )
                cif_id = UUID(str(current["cif_id"]))
                client_id = UUID(str(current["client_id"]))
                cursor.execute(
                    """
                    insert into restricted_identity.cif_verification_evidence (
                        cif_id, client_id, evidence_type,
                        verification_method, verification_result,
                        checked_at, document_date, document_expires_at,
                        masked_reference, external_evidence_reference,
                        evidence_sha256, retention_class, retain_until,
                        legal_hold, verified_by_user_id,
                        supersedes_evidence_id, created_by_user_id
                    ) values (
                        %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    returning *
                    """,
                    (
                        cif_id,
                        client_id,
                        normalized.evidence_type,
                        normalized.verification_method,
                        normalized.verification_result,
                        normalized.checked_at,
                        normalized.document_date,
                        normalized.document_expires_at,
                        normalized.masked_reference,
                        normalized.external_evidence_reference,
                        normalized.evidence_sha256,
                        normalized.retention_class,
                        normalized.retain_until,
                        normalized.legal_hold,
                        actor_user_id,
                        evidence_id,
                        actor_user_id,
                    ),
                )
                replacement_row = cursor.fetchone()
                cursor.execute(
                    """
                    update restricted_identity.cif_verification_evidence
                    set review_state = 'superseded'
                    where id = %s and review_state = 'verified'
                    """,
                    (evidence_id,),
                )
                if cursor.rowcount != 1:
                    raise RestrictedEvidenceConflict(
                        "Evidence changed during supersession"
                    )
                replacement_id = UUID(str(replacement_row["id"]))
                self._insert_access_event(
                    cursor,
                    evidence_id=evidence_id,
                    cif_id=cif_id,
                    client_id=client_id,
                    actor_user_id=actor_user_id,
                    registered_device_id=registered_device_id,
                    action="supersede",
                    purpose_code=purpose,
                    request_id=request_id,
                )
                self._insert_access_event(
                    cursor,
                    evidence_id=replacement_id,
                    cif_id=cif_id,
                    client_id=client_id,
                    actor_user_id=actor_user_id,
                    registered_device_id=registered_device_id,
                    action="create",
                    purpose_code=purpose,
                    request_id=request_id,
                )
                return _record_from_row(replacement_row)

    @staticmethod
    def _client_for_cif(cursor: Any, *, cif_id: UUID) -> UUID:
        cursor.execute(
            """
            select client_id
            from lending.client_information_forms
            where id = %s
            """,
            (cif_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise RestrictedEvidenceNotFound(
                "Client Information Form was not found"
            )
        return UUID(str(row["client_id"]))

    @staticmethod
    def _select_locked(
        cursor: Any,
        *,
        evidence_id: UUID,
        for_update: bool,
    ) -> Mapping[str, object]:
        suffix = " for update" if for_update else ""
        cursor.execute(
            """
            select *
            from restricted_identity.cif_verification_evidence
            where id = %s
            """
            + suffix,
            (evidence_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise RestrictedEvidenceNotFound(
                "Restricted verification evidence was not found"
            )
        return row

    @staticmethod
    def _insert_access_event(
        cursor: Any,
        *,
        evidence_id: UUID | None,
        cif_id: UUID,
        client_id: UUID,
        actor_user_id: UUID,
        registered_device_id: UUID,
        action: str,
        purpose_code: str,
        request_id: UUID,
    ) -> None:
        if action not in _ACTIONS:
            raise RestrictedEvidenceValidationError(
                "unsupported restricted evidence action"
            )
        cursor.execute(
            """
            insert into restricted_identity.evidence_access_events (
                evidence_id, cif_id, client_id, actor_user_id,
                registered_device_id, action, purpose_code, request_id
            ) values (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                evidence_id,
                cif_id,
                client_id,
                actor_user_id,
                registered_device_id,
                action,
                purpose_code,
                request_id,
            ),
        )
