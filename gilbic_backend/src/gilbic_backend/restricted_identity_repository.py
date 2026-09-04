from __future__ import annotations

import re
from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Iterator, Literal
from uuid import UUID

from psycopg import errors
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .cif_domain import (
    ALLOWED_ACCESS_PURPOSES,
    ALLOWED_EVIDENCE_TYPES,
    normalize_masked_reference,
)
from .database import open_connection


EvidenceDecision = Literal["approved", "rejected"]
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_OUTCOMES = frozenset(
    {"verified", "not_verified", "inconclusive", "exception_approved"}
)
_ALLOWED_RETENTION_CLASSES = frozenset(
    {"identity_verification", "residence_verification", "approved_exception"}
)


class RestrictedIdentityError(RuntimeError):
    code = "restricted_identity_error"


class RestrictedIdentityNotFound(RestrictedIdentityError):
    code = "restricted_identity_not_found"


class RestrictedIdentityConflict(RestrictedIdentityError):
    code = "restricted_identity_conflict"


class RestrictedIdentityInvalid(RestrictedIdentityError):
    code = "restricted_identity_invalid"


@dataclass(frozen=True, slots=True)
class RestrictedEvidenceData:
    evidence_type: str
    verification_method: str
    verification_outcome: str
    checked_at: datetime
    document_date: date | None
    document_expires_at: date | None
    masked_reference: str
    external_evidence_reference: str
    evidence_digest: str
    retention_class: str
    retain_until: date
    legal_hold: bool
    supersedes_evidence_id: UUID | None


@dataclass(frozen=True, slots=True)
class RestrictedEvidenceRecord:
    evidence_id: UUID
    client_id: UUID
    cif_id: UUID
    evidence_type: str
    verification_method: str
    verification_outcome: str
    checked_at: datetime
    document_date: date | None
    document_expires_at: date | None
    masked_reference: str
    external_evidence_reference: str
    evidence_digest: str
    retention_class: str
    retain_until: date
    legal_hold: bool
    recorded_by_user_id: UUID
    recorded_at: datetime
    supersedes_evidence_id: UUID | None
    review_decision: EvidenceDecision | None
    review_note: str | None
    reviewed_by_user_id: UUID | None
    reviewed_at: datetime | None
    is_superseded: bool


class PostgresRestrictedIdentityRepository:
    def list_for_cif(
        self,
        *,
        actor_user_id: UUID,
        registered_device_id: UUID,
        request_id: UUID,
        purpose_code: str,
        cif_id: UUID,
    ) -> tuple[RestrictedEvidenceRecord, ...]:
        purpose = self._normalize_purpose(purpose_code)
        with self._connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                self._require_cif(cursor, cif_id=cif_id)
                cursor.execute(
                    self._record_select()
                    + " where evidence.cif_id = %s order by evidence.recorded_at desc, evidence.id desc",
                    (cif_id,),
                )
                records = tuple(
                    self._record_from_row(row) for row in cursor.fetchall()
                )
                for record in records:
                    self._write_access(
                        cursor,
                        actor_user_id=actor_user_id,
                        evidence_id=record.evidence_id,
                        action="view",
                        purpose_code=purpose,
                        registered_device_id=registered_device_id,
                        request_id=request_id,
                    )
                return records

    def record(
        self,
        *,
        actor_user_id: UUID,
        registered_device_id: UUID,
        request_id: UUID,
        purpose_code: str,
        client_id: UUID,
        cif_id: UUID,
        data: RestrictedEvidenceData,
    ) -> RestrictedEvidenceRecord:
        purpose = self._normalize_purpose(purpose_code)
        normalized = self._normalize_data(data)
        with self._connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select client_id
                    from lending.client_information_forms
                    where id = %s
                    """,
                    (cif_id,),
                )
                cif = cursor.fetchone()
                if cif is None:
                    raise RestrictedIdentityNotFound(
                        "The Client Information Form was not found."
                    )
                if cif["client_id"] != client_id:
                    raise RestrictedIdentityInvalid(
                        "Restricted evidence client and CIF must match."
                    )
                cursor.execute(
                    """
                    insert into restricted_identity.cif_verification_evidence (
                        client_id,
                        cif_id,
                        evidence_type,
                        verification_method,
                        verification_outcome,
                        checked_at,
                        document_date,
                        document_expires_at,
                        masked_reference,
                        external_evidence_reference,
                        evidence_digest,
                        retention_class,
                        retain_until,
                        legal_hold,
                        recorded_by_user_id,
                        supersedes_evidence_id
                    ) values (
                        %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    returning id
                    """,
                    (
                        client_id,
                        cif_id,
                        normalized.evidence_type,
                        normalized.verification_method,
                        normalized.verification_outcome,
                        normalized.checked_at,
                        normalized.document_date,
                        normalized.document_expires_at,
                        normalized.masked_reference,
                        normalized.external_evidence_reference,
                        normalized.evidence_digest,
                        normalized.retention_class,
                        normalized.retain_until,
                        normalized.legal_hold,
                        actor_user_id,
                        normalized.supersedes_evidence_id,
                    ),
                )
                evidence_id = cursor.fetchone()["id"]
                self._write_access(
                    cursor,
                    actor_user_id=actor_user_id,
                    evidence_id=evidence_id,
                    action="record",
                    purpose_code=purpose,
                    registered_device_id=registered_device_id,
                    request_id=request_id,
                )
                self._audit(
                    cursor,
                    actor_user_id=actor_user_id,
                    action="identity_evidence.recorded",
                    target_id=evidence_id,
                    details={
                        "client_id": str(client_id),
                        "cif_id": str(cif_id),
                        "evidence_type": normalized.evidence_type,
                        "purpose_code": purpose,
                    },
                )
                return self._fetch_record(cursor, evidence_id=evidence_id)

    def review(
        self,
        *,
        actor_user_id: UUID,
        registered_device_id: UUID,
        request_id: UUID,
        purpose_code: str,
        evidence_id: UUID,
        decision: str,
        review_note: str,
    ) -> RestrictedEvidenceRecord:
        purpose = self._normalize_purpose(purpose_code)
        normalized_decision = decision.strip().lower()
        if normalized_decision not in {"approved", "rejected"}:
            raise RestrictedIdentityInvalid(
                "Restricted evidence review must be approved or rejected."
            )
        note = self._normalize_text(
            review_note,
            name="Review note",
            maximum=1000,
            required=True,
        )
        with self._connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select id, client_id, cif_id, recorded_by_user_id
                    from restricted_identity.cif_verification_evidence
                    where id = %s
                    for update
                    """,
                    (evidence_id,),
                )
                evidence = cursor.fetchone()
                if evidence is None:
                    raise RestrictedIdentityNotFound(
                        "The restricted evidence record was not found."
                    )
                if evidence["recorded_by_user_id"] == actor_user_id:
                    raise RestrictedIdentityConflict(
                        "Restricted evidence reviewer must differ from the recorder."
                    )
                cursor.execute(
                    """
                    insert into restricted_identity.cif_verification_evidence_reviews (
                        evidence_id,
                        review_decision,
                        review_note,
                        reviewed_by_user_id
                    ) values (%s, %s, %s, %s)
                    """,
                    (evidence_id, normalized_decision, note, actor_user_id),
                )
                self._write_access(
                    cursor,
                    actor_user_id=actor_user_id,
                    evidence_id=evidence_id,
                    action="review",
                    purpose_code=purpose,
                    registered_device_id=registered_device_id,
                    request_id=request_id,
                )
                self._audit(
                    cursor,
                    actor_user_id=actor_user_id,
                    action="identity_evidence.reviewed",
                    target_id=evidence_id,
                    details={
                        "client_id": str(evidence["client_id"]),
                        "cif_id": str(evidence["cif_id"]),
                        "decision": normalized_decision,
                        "purpose_code": purpose,
                    },
                )
                return self._fetch_record(cursor, evidence_id=evidence_id)

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        try:
            with open_connection() as connection:
                yield connection
        except errors.UniqueViolation as error:
            raise RestrictedIdentityConflict(
                "This restricted evidence action conflicts with an existing record."
            ) from error
        except errors.ForeignKeyViolation as error:
            raise RestrictedIdentityInvalid(
                "A referenced CIF, client, user, device, or evidence record does not exist."
            ) from error
        except errors.CheckViolation as error:
            raise RestrictedIdentityInvalid(
                "The restricted evidence data violates a protected validation rule."
            ) from error
        except errors.RaiseException as error:
            message = (
                error.diag.message_primary
                or "The protected restricted-evidence operation was rejected."
            )
            raise RestrictedIdentityConflict(message) from error

    @staticmethod
    def _record_select() -> str:
        return """
            select
                evidence.id as evidence_id,
                evidence.client_id,
                evidence.cif_id,
                evidence.evidence_type,
                evidence.verification_method,
                evidence.verification_outcome,
                evidence.checked_at,
                evidence.document_date,
                evidence.document_expires_at,
                evidence.masked_reference,
                evidence.external_evidence_reference,
                evidence.evidence_digest,
                evidence.retention_class,
                evidence.retain_until,
                evidence.legal_hold,
                evidence.recorded_by_user_id,
                evidence.recorded_at,
                evidence.supersedes_evidence_id,
                evidence.review_decision,
                evidence.review_note,
                evidence.reviewed_by_user_id,
                evidence.reviewed_at,
                evidence.is_superseded
            from restricted_identity.cif_verification_evidence_status evidence
        """

    def _fetch_record(self, cursor, *, evidence_id: UUID) -> RestrictedEvidenceRecord:
        cursor.execute(
            self._record_select() + " where evidence.id = %s",
            (evidence_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise RestrictedIdentityNotFound(
                "The restricted evidence record was not found."
            )
        return self._record_from_row(row)

    @staticmethod
    def _record_from_row(row: Mapping[str, Any]) -> RestrictedEvidenceRecord:
        decision = (
            str(row["review_decision"])
            if row["review_decision"] is not None
            else None
        )
        return RestrictedEvidenceRecord(
            evidence_id=row["evidence_id"],
            client_id=row["client_id"],
            cif_id=row["cif_id"],
            evidence_type=str(row["evidence_type"]),
            verification_method=str(row["verification_method"]),
            verification_outcome=str(row["verification_outcome"]),
            checked_at=row["checked_at"],
            document_date=row["document_date"],
            document_expires_at=row["document_expires_at"],
            masked_reference=str(row["masked_reference"]),
            external_evidence_reference=str(row["external_evidence_reference"]),
            evidence_digest=str(row["evidence_digest"]).strip(),
            retention_class=str(row["retention_class"]),
            retain_until=row["retain_until"],
            legal_hold=bool(row["legal_hold"]),
            recorded_by_user_id=row["recorded_by_user_id"],
            recorded_at=row["recorded_at"],
            supersedes_evidence_id=row["supersedes_evidence_id"],
            review_decision=decision,  # type: ignore[arg-type]
            review_note=(
                str(row["review_note"]) if row["review_note"] is not None else None
            ),
            reviewed_by_user_id=row["reviewed_by_user_id"],
            reviewed_at=row["reviewed_at"],
            is_superseded=bool(row["is_superseded"]),
        )

    @staticmethod
    def _require_cif(cursor, *, cif_id: UUID) -> None:
        cursor.execute(
            "select 1 from lending.client_information_forms where id = %s",
            (cif_id,),
        )
        if cursor.fetchone() is None:
            raise RestrictedIdentityNotFound(
                "The Client Information Form was not found."
            )

    @classmethod
    def _normalize_data(cls, data: RestrictedEvidenceData) -> RestrictedEvidenceData:
        evidence_type = data.evidence_type.strip().lower()
        if evidence_type not in ALLOWED_EVIDENCE_TYPES:
            raise RestrictedIdentityInvalid("Select an approved evidence type.")
        method = cls._normalize_text(
            data.verification_method,
            name="Verification method",
            maximum=120,
            required=True,
        )
        outcome = data.verification_outcome.strip().lower()
        if outcome not in _ALLOWED_OUTCOMES:
            raise RestrictedIdentityInvalid(
                "Select an approved verification outcome."
            )
        cls._require_aware(data.checked_at, name="checked_at")
        try:
            masked = normalize_masked_reference(data.masked_reference)
        except ValueError as error:
            raise RestrictedIdentityInvalid(str(error)) from error
        external_reference = cls._normalize_text(
            data.external_evidence_reference,
            name="External evidence reference",
            maximum=500,
            required=True,
        )
        digest = data.evidence_digest.strip().lower()
        if not _HEX_64.fullmatch(digest):
            raise RestrictedIdentityInvalid(
                "Evidence digest must be lowercase SHA-256."
            )
        retention_class = data.retention_class.strip().lower()
        if retention_class not in _ALLOWED_RETENTION_CLASSES:
            raise RestrictedIdentityInvalid("Select an approved retention class.")
        if (
            data.document_date is not None
            and data.document_expires_at is not None
            and data.document_expires_at < data.document_date
        ):
            raise RestrictedIdentityInvalid(
                "Document expiry cannot be earlier than document date."
            )
        if data.retain_until < data.checked_at.date():
            raise RestrictedIdentityInvalid(
                "Retention date cannot be earlier than the evidence check date."
            )
        return RestrictedEvidenceData(
            evidence_type=evidence_type,
            verification_method=method,
            verification_outcome=outcome,
            checked_at=data.checked_at.astimezone(UTC),
            document_date=data.document_date,
            document_expires_at=data.document_expires_at,
            masked_reference=masked,
            external_evidence_reference=external_reference,
            evidence_digest=digest,
            retention_class=retention_class,
            retain_until=data.retain_until,
            legal_hold=bool(data.legal_hold),
            supersedes_evidence_id=data.supersedes_evidence_id,
        )

    @staticmethod
    def _normalize_purpose(value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in ALLOWED_ACCESS_PURPOSES:
            raise RestrictedIdentityInvalid(
                "Select an approved access purpose for restricted evidence."
            )
        return normalized

    @staticmethod
    def _normalize_text(
        value: str,
        *,
        name: str,
        maximum: int,
        required: bool,
    ) -> str:
        if any(ord(character) < 32 or ord(character) == 127 for character in value):
            raise RestrictedIdentityInvalid(
                f"{name} cannot contain control characters."
            )
        normalized = " ".join(value.split())
        if required and not normalized:
            raise RestrictedIdentityInvalid(f"{name} is required.")
        if len(normalized) > maximum:
            raise RestrictedIdentityInvalid(
                f"{name} cannot exceed {maximum} characters."
            )
        return normalized

    @staticmethod
    def _require_aware(value: datetime, *, name: str) -> None:
        if value.tzinfo is None or value.utcoffset() is None:
            raise RestrictedIdentityInvalid(f"{name} must be timezone-aware.")

    @staticmethod
    def _write_access(
        cursor,
        *,
        actor_user_id: UUID,
        evidence_id: UUID,
        action: str,
        purpose_code: str,
        registered_device_id: UUID,
        request_id: UUID,
    ) -> None:
        cursor.execute(
            """
            insert into restricted_identity.evidence_access_events (
                actor_user_id,
                evidence_id,
                action,
                purpose_code,
                registered_device_id,
                request_id
            ) values (%s, %s, %s, %s, %s, %s)
            on conflict (request_id, evidence_id, action) do nothing
            """,
            (
                actor_user_id,
                evidence_id,
                action,
                purpose_code,
                registered_device_id,
                request_id,
            ),
        )

    @staticmethod
    def _audit(
        cursor,
        *,
        actor_user_id: UUID,
        action: str,
        target_id: UUID,
        details: dict[str, object],
    ) -> None:
        cursor.execute(
            """
            insert into core.audit_logs (
                actor_user_id,
                action,
                target_type,
                target_id,
                details
            ) values (%s, %s, 'restricted_identity_evidence', %s, %s)
            """,
            (actor_user_id, action, target_id, Jsonb(details)),
        )
