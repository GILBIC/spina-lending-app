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
    ALLOWED_REVERIFICATION_REASONS,
    canonical_cif_digest,
)
from .database import open_connection


CifRequirementStatus = Literal["open", "resolved"]
CifRequirementSeverity = Literal["standard", "high"]
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_ADDRESS_KEYS = frozenset(
    {
        "line1",
        "line2",
        "barangay",
        "city_municipality",
        "province",
        "postal_code",
        "landmark",
    }
)
_LIVELIHOOD_KEYS = frozenset(
    {
        "kind",
        "employer_or_business",
        "position_or_activity",
        "description",
        "years_active",
    }
)


class CifError(RuntimeError):
    code = "cif_error"


class CifNotFound(CifError):
    code = "cif_not_found"


class CifConflict(CifError):
    code = "cif_conflict"


class CifInvalid(CifError):
    code = "cif_invalid"


@dataclass(frozen=True, slots=True)
class CifDraftData:
    legal_full_name: str
    birth_date: date | None
    place_of_birth: str
    nationality: str
    civil_status: str
    phone_number: str
    email: str | None
    present_address: dict[str, object]
    permanent_address: dict[str, object]
    same_as_present_address: bool
    livelihood_profile: dict[str, object]
    privacy_notice_version: str
    privacy_acknowledged_at: datetime | None
    client_signature_reference: str
    client_signature_digest: str | None
    form_schema_version: str = "1"


@dataclass(frozen=True, slots=True)
class CifClientSummary:
    client_id: UUID
    client_code: str
    client_name: str
    area: str
    client_status: str
    active_cif_id: UUID | None
    active_cif_number: str | None
    active_cif_status: str | None
    active_cif_expires_at: datetime | None
    is_eligible_for_new_credit: bool


@dataclass(frozen=True, slots=True)
class ClientInformationFormRecord:
    cif_id: UUID
    cif_number: str
    client_id: UUID
    client_code: str
    client_name: str
    form_version: int
    lifecycle_state: str
    public_status: str
    effective_at: datetime | None
    expires_at: datetime | None
    supersedes_cif_id: UUID | None
    legal_full_name: str
    birth_date: date | None
    place_of_birth: str
    nationality: str
    civil_status: str
    phone_number: str
    email: str | None
    present_address: dict[str, object]
    permanent_address: dict[str, object]
    same_as_present_address: bool
    livelihood_profile: dict[str, object]
    privacy_notice_version: str
    privacy_acknowledged_at: datetime | None
    has_client_signature: bool
    prepared_by_user_id: UUID
    verified_by_user_id: UUID | None
    verified_at: datetime | None
    approved_by_user_id: UUID | None
    approved_at: datetime | None
    form_schema_version: str
    source_digest: str | None
    has_open_reverification: bool
    is_eligible_for_new_credit: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class CifReverificationRecord:
    requirement_id: UUID
    client_id: UUID
    source_cif_id: UUID | None
    reason: str
    severity: CifRequirementSeverity
    status: CifRequirementStatus
    note: str
    opened_by_user_id: UUID
    opened_at: datetime
    resolved_by_user_id: UUID | None
    resolved_at: datetime | None
    resolution_cif_id: UUID | None
    resolution_note: str


class PostgresCifRepository:
    def search_clients(
        self,
        *,
        query: str,
        limit: int = 50,
    ) -> tuple[CifClientSummary, ...]:
        normalized_query = query.strip()
        if not 1 <= limit <= 100:
            raise CifInvalid("Client search limit must be between 1 and 100.")
        pattern = f"%{normalized_query}%"
        with self._connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select
                        client.id as client_id,
                        client.client_code,
                        client.full_name as client_name,
                        coalesce(client.area, '') as area,
                        client.status as client_status,
                        active_cif.id as active_cif_id,
                        active_cif.cif_number as active_cif_number,
                        active_cif.public_status as active_cif_status,
                        active_cif.expires_at as active_cif_expires_at,
                        coalesce(active_cif.is_eligible_for_new_credit, false)
                            as is_eligible_for_new_credit
                    from lending.clients client
                    left join lateral (
                        select status.*
                        from lending.client_information_form_status status
                        where status.client_id = client.id
                          and status.lifecycle_state = 'active'
                        order by status.form_version desc
                        limit 1
                    ) active_cif on true
                    where (
                        %s = ''
                        or client.client_code ilike %s
                        or client.full_name ilike %s
                    )
                    order by client.client_code, client.id
                    limit %s
                    """,
                    (normalized_query, pattern, pattern, limit),
                )
                return tuple(
                    CifClientSummary(
                        client_id=row["client_id"],
                        client_code=str(row["client_code"]),
                        client_name=str(row["client_name"]),
                        area=str(row["area"]),
                        client_status=str(row["client_status"]),
                        active_cif_id=row["active_cif_id"],
                        active_cif_number=(
                            str(row["active_cif_number"])
                            if row["active_cif_number"] is not None
                            else None
                        ),
                        active_cif_status=(
                            str(row["active_cif_status"])
                            if row["active_cif_status"] is not None
                            else None
                        ),
                        active_cif_expires_at=row["active_cif_expires_at"],
                        is_eligible_for_new_credit=bool(
                            row["is_eligible_for_new_credit"]
                        ),
                    )
                    for row in cursor.fetchall()
                )

    def list_for_client(
        self,
        *,
        client_id: UUID,
    ) -> tuple[ClientInformationFormRecord, ...]:
        with self._connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                self._require_client(cursor, client_id=client_id)
                cursor.execute(
                    self._record_select()
                    + " where status.client_id = %s order by status.form_version desc",
                    (client_id,),
                )
                return tuple(self._record_from_row(row) for row in cursor.fetchall())

    def get(self, *, cif_id: UUID) -> ClientInformationFormRecord:
        with self._connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                return self._fetch_record(cursor, cif_id=cif_id)

    def list_reverification_for_client(
        self,
        *,
        client_id: UUID,
    ) -> tuple[CifReverificationRecord, ...]:
        with self._connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                self._require_client(cursor, client_id=client_id)
                cursor.execute(
                    """
                    select
                        id as requirement_id,
                        client_id,
                        source_cif_id,
                        reason,
                        severity,
                        status,
                        note,
                        opened_by_user_id,
                        opened_at,
                        resolved_by_user_id,
                        resolved_at,
                        resolution_cif_id,
                        resolution_note
                    from lending.client_cif_reverification_requirements
                    where client_id = %s
                    order by opened_at desc, id desc
                    """,
                    (client_id,),
                )
                return tuple(
                    self._requirement_from_row(row) for row in cursor.fetchall()
                )

    def create_draft(
        self,
        *,
        actor_user_id: UUID,
        client_id: UUID,
        draft: CifDraftData,
    ) -> ClientInformationFormRecord:
        normalized = self._normalize_draft(draft)
        with self._connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                self._lock_client(cursor, client_id=client_id)
                cursor.execute(
                    """
                    select id
                    from lending.client_information_forms
                    where client_id = %s
                      and lifecycle_state = 'draft'
                    """,
                    (client_id,),
                )
                if cursor.fetchone() is not None:
                    raise CifConflict(
                        "This client already has a draft CIF. Open or replace that draft first."
                    )
                cursor.execute(
                    """
                    select
                        coalesce(max(form_version), 0) + 1 as next_version,
                        max(id) filter (where lifecycle_state = 'active') as active_cif_id
                    from lending.client_information_forms
                    where client_id = %s
                    """,
                    (client_id,),
                )
                version_row = cursor.fetchone()
                cursor.execute(
                    """
                    insert into lending.client_information_forms (
                        client_id,
                        form_version,
                        supersedes_cif_id,
                        legal_full_name,
                        birth_date,
                        place_of_birth,
                        nationality,
                        civil_status,
                        phone_number,
                        email,
                        present_address,
                        permanent_address,
                        same_as_present_address,
                        livelihood_profile,
                        privacy_notice_version,
                        privacy_acknowledged_at,
                        client_signature_reference,
                        client_signature_digest,
                        prepared_by_user_id,
                        form_schema_version
                    ) values (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    returning id
                    """,
                    (
                        client_id,
                        int(version_row["next_version"]),
                        version_row["active_cif_id"],
                        normalized.legal_full_name,
                        normalized.birth_date,
                        normalized.place_of_birth,
                        normalized.nationality,
                        normalized.civil_status,
                        normalized.phone_number,
                        normalized.email,
                        Jsonb(normalized.present_address),
                        Jsonb(normalized.permanent_address),
                        normalized.same_as_present_address,
                        Jsonb(normalized.livelihood_profile),
                        normalized.privacy_notice_version,
                        normalized.privacy_acknowledged_at,
                        normalized.client_signature_reference,
                        normalized.client_signature_digest,
                        actor_user_id,
                        normalized.form_schema_version,
                    ),
                )
                cif_id = cursor.fetchone()["id"]
                self._audit(
                    cursor,
                    actor_user_id=actor_user_id,
                    action="cif.draft_created",
                    target_type="client_information_form",
                    target_id=cif_id,
                    details={
                        "client_id": str(client_id),
                        "form_version": int(version_row["next_version"]),
                        "reason_code": "new_or_replacement_cif",
                    },
                )
                return self._fetch_record(cursor, cif_id=cif_id)

    def update_draft(
        self,
        *,
        actor_user_id: UUID,
        cif_id: UUID,
        expected_updated_at: datetime,
        draft: CifDraftData,
    ) -> ClientInformationFormRecord:
        self._require_aware(expected_updated_at, name="expected_updated_at")
        normalized = self._normalize_draft(draft)
        with self._connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    update lending.client_information_forms
                    set legal_full_name = %s,
                        birth_date = %s,
                        place_of_birth = %s,
                        nationality = %s,
                        civil_status = %s,
                        phone_number = %s,
                        email = %s,
                        present_address = %s,
                        permanent_address = %s,
                        same_as_present_address = %s,
                        livelihood_profile = %s,
                        privacy_notice_version = %s,
                        privacy_acknowledged_at = %s,
                        client_signature_reference = %s,
                        client_signature_digest = %s,
                        form_schema_version = %s,
                        verified_by_user_id = null,
                        verified_at = null,
                        verification_note = '',
                        source_digest = null,
                        updated_at = now()
                    where id = %s
                      and lifecycle_state = 'draft'
                      and updated_at = %s
                    returning client_id, form_version
                    """,
                    (
                        normalized.legal_full_name,
                        normalized.birth_date,
                        normalized.place_of_birth,
                        normalized.nationality,
                        normalized.civil_status,
                        normalized.phone_number,
                        normalized.email,
                        Jsonb(normalized.present_address),
                        Jsonb(normalized.permanent_address),
                        normalized.same_as_present_address,
                        Jsonb(normalized.livelihood_profile),
                        normalized.privacy_notice_version,
                        normalized.privacy_acknowledged_at,
                        normalized.client_signature_reference,
                        normalized.client_signature_digest,
                        normalized.form_schema_version,
                        cif_id,
                        expected_updated_at,
                    ),
                )
                changed = cursor.fetchone()
                if changed is None:
                    self._raise_missing_or_changed(cursor, cif_id=cif_id)
                self._audit(
                    cursor,
                    actor_user_id=actor_user_id,
                    action="cif.draft_updated",
                    target_type="client_information_form",
                    target_id=cif_id,
                    details={
                        "client_id": str(changed["client_id"]),
                        "form_version": int(changed["form_version"]),
                        "verification_reset": True,
                    },
                )
                return self._fetch_record(cursor, cif_id=cif_id)

    def verify(
        self,
        *,
        actor_user_id: UUID,
        cif_id: UUID,
        expected_updated_at: datetime,
        review_note: str,
    ) -> ClientInformationFormRecord:
        self._require_aware(expected_updated_at, name="expected_updated_at")
        note = self._normalize_text(
            review_note,
            name="Verification note",
            maximum=1000,
            required=True,
        )
        with self._connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                row = self._lock_cif(cursor, cif_id=cif_id)
                if row["lifecycle_state"] != "draft":
                    raise CifConflict("Only a draft CIF can be verified.")
                if row["updated_at"] != expected_updated_at:
                    raise CifConflict("The CIF changed. Refresh before verifying it.")
                self._assert_complete(row)
                digest = canonical_cif_digest(self._source_payload(row))
                cursor.execute(
                    """
                    update lending.client_information_forms
                    set verified_by_user_id = %s,
                        verified_at = now(),
                        verification_note = %s,
                        source_digest = %s,
                        updated_at = now()
                    where id = %s
                    """,
                    (actor_user_id, note, digest, cif_id),
                )
                self._audit(
                    cursor,
                    actor_user_id=actor_user_id,
                    action="cif.verified",
                    target_type="client_information_form",
                    target_id=cif_id,
                    details={
                        "client_id": str(row["client_id"]),
                        "form_version": int(row["form_version"]),
                        "source_digest": digest,
                    },
                )
                return self._fetch_record(cursor, cif_id=cif_id)

    def activate(
        self,
        *,
        actor_user_id: UUID,
        cif_id: UUID,
        expected_source_digest: str,
        review_note: str,
    ) -> ClientInformationFormRecord:
        digest = expected_source_digest.strip().lower()
        if not _HEX_64.fullmatch(digest):
            raise CifInvalid("A valid verified CIF source digest is required.")
        note = self._normalize_text(
            review_note,
            name="Approval note",
            maximum=1000,
            required=True,
        )
        with self._connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                row = self._lock_cif(cursor, cif_id=cif_id)
                if row["lifecycle_state"] != "draft":
                    raise CifConflict("Only a verified draft CIF can be activated.")
                if row["verified_by_user_id"] is None or row["source_digest"] is None:
                    raise CifConflict("The CIF must be verified before activation.")
                if row["verified_by_user_id"] == actor_user_id:
                    raise CifConflict(
                        "CIF activation requires different verifier and approver users."
                    )
                self._assert_complete(row)
                current_digest = canonical_cif_digest(self._source_payload(row))
                stored_digest = str(row["source_digest"]).strip().lower()
                if digest != stored_digest or digest != current_digest:
                    raise CifConflict(
                        "The verified CIF source changed. Verify the current version again."
                    )

                self._lock_client(cursor, client_id=row["client_id"])
                cursor.execute(
                    """
                    select id
                    from lending.client_information_forms
                    where client_id = %s
                      and lifecycle_state = 'active'
                      and id <> %s
                    for update
                    """,
                    (row["client_id"], cif_id),
                )
                prior = cursor.fetchone()
                if prior is not None:
                    cursor.execute(
                        """
                        update lending.client_information_forms
                        set lifecycle_state = 'superseded'
                        where id = %s
                        """,
                        (prior["id"],),
                    )

                cursor.execute(
                    """
                    update lending.client_information_forms
                    set lifecycle_state = 'active',
                        effective_at = now(),
                        expires_at = now() + interval '5 years',
                        approved_by_user_id = %s,
                        approved_at = now(),
                        approval_note = %s,
                        updated_at = now()
                    where id = %s
                    """,
                    (actor_user_id, note, cif_id),
                )
                cursor.execute(
                    """
                    update lending.client_cif_reverification_requirements
                    set status = 'resolved',
                        resolved_by_user_id = %s,
                        resolved_at = now(),
                        resolution_cif_id = %s,
                        resolution_note = %s
                    where client_id = %s
                      and status = 'open'
                    """,
                    (actor_user_id, cif_id, note, row["client_id"]),
                )
                self._audit(
                    cursor,
                    actor_user_id=actor_user_id,
                    action="cif.activated",
                    target_type="client_information_form",
                    target_id=cif_id,
                    details={
                        "client_id": str(row["client_id"]),
                        "form_version": int(row["form_version"]),
                        "source_digest": digest,
                        "superseded_cif_id": (
                            str(prior["id"]) if prior is not None else None
                        ),
                    },
                )
                return self._fetch_record(cursor, cif_id=cif_id)

    def open_reverification(
        self,
        *,
        actor_user_id: UUID,
        client_id: UUID,
        reason: str,
        severity: str,
        note: str,
    ) -> CifReverificationRecord:
        normalized_reason = reason.strip().lower()
        if normalized_reason not in ALLOWED_REVERIFICATION_REASONS:
            raise CifInvalid("Select an approved CIF re-verification reason.")
        normalized_severity = severity.strip().lower()
        if normalized_severity not in {"standard", "high"}:
            raise CifInvalid("CIF re-verification severity must be standard or high.")
        normalized_note = self._normalize_text(
            note,
            name="Re-verification note",
            maximum=1000,
            required=True,
        )
        with self._connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                self._lock_client(cursor, client_id=client_id)
                cursor.execute(
                    """
                    select id
                    from lending.client_information_forms
                    where client_id = %s
                      and lifecycle_state = 'active'
                    limit 1
                    """,
                    (client_id,),
                )
                source = cursor.fetchone()
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
                    returning
                        id as requirement_id,
                        client_id,
                        source_cif_id,
                        reason,
                        severity,
                        status,
                        note,
                        opened_by_user_id,
                        opened_at,
                        resolved_by_user_id,
                        resolved_at,
                        resolution_cif_id,
                        resolution_note
                    """,
                    (
                        client_id,
                        source["id"] if source is not None else None,
                        normalized_reason,
                        normalized_severity,
                        normalized_note,
                        actor_user_id,
                    ),
                )
                requirement = cursor.fetchone()
                self._audit(
                    cursor,
                    actor_user_id=actor_user_id,
                    action="cif.reverification_opened",
                    target_type="client_cif_reverification",
                    target_id=requirement["requirement_id"],
                    details={
                        "client_id": str(client_id),
                        "source_cif_id": (
                            str(source["id"]) if source is not None else None
                        ),
                        "reason_code": normalized_reason,
                        "severity": normalized_severity,
                    },
                )
                return self._requirement_from_row(requirement)

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        try:
            with open_connection() as connection:
                yield connection
        except errors.UniqueViolation as error:
            raise CifConflict(
                "A conflicting CIF version or re-verification requirement already exists."
            ) from error
        except errors.ForeignKeyViolation as error:
            raise CifInvalid("A referenced CIF, client, or user does not exist.") from error
        except errors.CheckViolation as error:
            raise CifInvalid("The CIF data violates a protected validation rule.") from error
        except errors.RaiseException as error:
            message = error.diag.message_primary or "The protected CIF operation was rejected."
            raise CifConflict(message) from error

    @staticmethod
    def _record_select() -> str:
        return """
            select
                status.id as cif_id,
                status.cif_number,
                status.client_id,
                client.client_code,
                client.full_name as client_name,
                status.form_version,
                status.lifecycle_state,
                status.public_status,
                status.effective_at,
                status.expires_at,
                status.supersedes_cif_id,
                status.legal_full_name,
                status.birth_date,
                status.place_of_birth,
                status.nationality,
                status.civil_status,
                status.phone_number,
                status.email,
                status.present_address,
                status.permanent_address,
                status.same_as_present_address,
                status.livelihood_profile,
                status.privacy_notice_version,
                status.privacy_acknowledged_at,
                (status.client_signature_reference <> ''
                    and status.client_signature_digest is not null)
                    as has_client_signature,
                status.prepared_by_user_id,
                status.verified_by_user_id,
                status.verified_at,
                status.approved_by_user_id,
                status.approved_at,
                status.form_schema_version,
                status.source_digest,
                status.has_open_reverification,
                status.is_eligible_for_new_credit,
                status.created_at,
                status.updated_at
            from lending.client_information_form_status status
            join lending.clients client on client.id = status.client_id
        """

    def _fetch_record(self, cursor, *, cif_id: UUID) -> ClientInformationFormRecord:
        cursor.execute(self._record_select() + " where status.id = %s", (cif_id,))
        row = cursor.fetchone()
        if row is None:
            raise CifNotFound("The Client Information Form was not found.")
        return self._record_from_row(row)

    @staticmethod
    def _record_from_row(row: Mapping[str, Any]) -> ClientInformationFormRecord:
        return ClientInformationFormRecord(
            cif_id=row["cif_id"],
            cif_number=str(row["cif_number"]),
            client_id=row["client_id"],
            client_code=str(row["client_code"]),
            client_name=str(row["client_name"]),
            form_version=int(row["form_version"]),
            lifecycle_state=str(row["lifecycle_state"]),
            public_status=str(row["public_status"]),
            effective_at=row["effective_at"],
            expires_at=row["expires_at"],
            supersedes_cif_id=row["supersedes_cif_id"],
            legal_full_name=str(row["legal_full_name"]),
            birth_date=row["birth_date"],
            place_of_birth=str(row["place_of_birth"]),
            nationality=str(row["nationality"]),
            civil_status=str(row["civil_status"]),
            phone_number=str(row["phone_number"]),
            email=str(row["email"]) if row["email"] is not None else None,
            present_address=dict(row["present_address"]),
            permanent_address=dict(row["permanent_address"]),
            same_as_present_address=bool(row["same_as_present_address"]),
            livelihood_profile=dict(row["livelihood_profile"]),
            privacy_notice_version=str(row["privacy_notice_version"]),
            privacy_acknowledged_at=row["privacy_acknowledged_at"],
            has_client_signature=bool(row["has_client_signature"]),
            prepared_by_user_id=row["prepared_by_user_id"],
            verified_by_user_id=row["verified_by_user_id"],
            verified_at=row["verified_at"],
            approved_by_user_id=row["approved_by_user_id"],
            approved_at=row["approved_at"],
            form_schema_version=str(row["form_schema_version"]),
            source_digest=(
                str(row["source_digest"]).strip()
                if row["source_digest"] is not None
                else None
            ),
            has_open_reverification=bool(row["has_open_reverification"]),
            is_eligible_for_new_credit=bool(row["is_eligible_for_new_credit"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _requirement_from_row(row: Mapping[str, Any]) -> CifReverificationRecord:
        return CifReverificationRecord(
            requirement_id=row["requirement_id"],
            client_id=row["client_id"],
            source_cif_id=row["source_cif_id"],
            reason=str(row["reason"]),
            severity=str(row["severity"]),  # type: ignore[arg-type]
            status=str(row["status"]),  # type: ignore[arg-type]
            note=str(row["note"]),
            opened_by_user_id=row["opened_by_user_id"],
            opened_at=row["opened_at"],
            resolved_by_user_id=row["resolved_by_user_id"],
            resolved_at=row["resolved_at"],
            resolution_cif_id=row["resolution_cif_id"],
            resolution_note=str(row["resolution_note"]),
        )

    @staticmethod
    def _require_client(cursor, *, client_id: UUID) -> None:
        cursor.execute("select 1 from lending.clients where id = %s", (client_id,))
        if cursor.fetchone() is None:
            raise CifNotFound("The client was not found.")

    @staticmethod
    def _lock_client(cursor, *, client_id: UUID) -> None:
        cursor.execute(
            "select id from lending.clients where id = %s for update",
            (client_id,),
        )
        if cursor.fetchone() is None:
            raise CifNotFound("The client was not found.")

    @staticmethod
    def _lock_cif(cursor, *, cif_id: UUID) -> Mapping[str, Any]:
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
            raise CifNotFound("The Client Information Form was not found.")
        return row

    @staticmethod
    def _raise_missing_or_changed(cursor, *, cif_id: UUID) -> None:
        cursor.execute(
            "select lifecycle_state, updated_at from lending.client_information_forms where id = %s",
            (cif_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise CifNotFound("The Client Information Form was not found.")
        if row["lifecycle_state"] != "draft":
            raise CifConflict("Only a draft CIF can be edited.")
        raise CifConflict("The CIF changed. Refresh before editing it again.")

    @classmethod
    def _normalize_draft(cls, draft: CifDraftData) -> CifDraftData:
        legal_name = cls._normalize_text(
            draft.legal_full_name,
            name="Legal full name",
            maximum=200,
            required=True,
        )
        place = cls._normalize_text(
            draft.place_of_birth,
            name="Place of birth",
            maximum=200,
            required=False,
        )
        nationality = cls._normalize_text(
            draft.nationality,
            name="Nationality",
            maximum=100,
            required=False,
        )
        civil_status = cls._normalize_text(
            draft.civil_status,
            name="Civil status",
            maximum=50,
            required=False,
        )
        phone = cls._normalize_text(
            draft.phone_number,
            name="Phone number",
            maximum=40,
            required=False,
        )
        email = (
            cls._normalize_text(
                draft.email,
                name="Email",
                maximum=254,
                required=False,
            )
            if draft.email is not None
            else None
        )
        if email == "":
            email = None
        present = cls._normalize_object(
            draft.present_address,
            name="Present address",
            allowed_keys=_ADDRESS_KEYS,
        )
        permanent = cls._normalize_object(
            draft.permanent_address,
            name="Permanent address",
            allowed_keys=_ADDRESS_KEYS,
        )
        livelihood = cls._normalize_object(
            draft.livelihood_profile,
            name="Livelihood profile",
            allowed_keys=_LIVELIHOOD_KEYS,
        )
        privacy_version = cls._normalize_text(
            draft.privacy_notice_version,
            name="Privacy notice version",
            maximum=100,
            required=False,
        )
        signature_reference = cls._normalize_text(
            draft.client_signature_reference,
            name="Client signature reference",
            maximum=500,
            required=False,
        )
        signature_digest = (
            draft.client_signature_digest.strip().lower()
            if draft.client_signature_digest is not None
            else None
        )
        if signature_digest == "":
            signature_digest = None
        if signature_digest is not None and not _HEX_64.fullmatch(signature_digest):
            raise CifInvalid("Client signature digest must be lowercase SHA-256.")
        if bool(signature_reference) != bool(signature_digest):
            raise CifInvalid(
                "Client signature reference and digest must be supplied together."
            )
        if draft.privacy_acknowledged_at is not None:
            cls._require_aware(
                draft.privacy_acknowledged_at,
                name="privacy_acknowledged_at",
            )
        schema_version = cls._normalize_text(
            draft.form_schema_version,
            name="Form schema version",
            maximum=50,
            required=True,
        )
        if draft.birth_date is not None and draft.birth_date > date.today():
            raise CifInvalid("Birth date cannot be in the future.")
        return CifDraftData(
            legal_full_name=legal_name,
            birth_date=draft.birth_date,
            place_of_birth=place,
            nationality=nationality,
            civil_status=civil_status,
            phone_number=phone,
            email=email,
            present_address=present,
            permanent_address=permanent,
            same_as_present_address=bool(draft.same_as_present_address),
            livelihood_profile=livelihood,
            privacy_notice_version=privacy_version,
            privacy_acknowledged_at=draft.privacy_acknowledged_at,
            client_signature_reference=signature_reference,
            client_signature_digest=signature_digest,
            form_schema_version=schema_version,
        )

    @staticmethod
    def _normalize_text(
        value: str,
        *,
        name: str,
        maximum: int,
        required: bool,
    ) -> str:
        if any(ord(character) < 32 or ord(character) == 127 for character in value):
            raise CifInvalid(f"{name} cannot contain control characters.")
        normalized = " ".join(value.split())
        if required and not normalized:
            raise CifInvalid(f"{name} is required.")
        if len(normalized) > maximum:
            raise CifInvalid(f"{name} cannot exceed {maximum} characters.")
        return normalized

    @classmethod
    def _normalize_object(
        cls,
        value: Mapping[str, object],
        *,
        name: str,
        allowed_keys: frozenset[str],
    ) -> dict[str, object]:
        if not isinstance(value, Mapping):
            raise CifInvalid(f"{name} must be an object.")
        unknown = set(value) - allowed_keys
        if unknown:
            raise CifInvalid(
                f"{name} contains unsupported fields: {', '.join(sorted(unknown))}."
            )
        normalized: dict[str, object] = {}
        for key, raw in value.items():
            if raw is None or isinstance(raw, (bool, int)):
                normalized[key] = raw
                continue
            if not isinstance(raw, str):
                raise CifInvalid(f"{name}.{key} must be text, a number, or null.")
            normalized[key] = cls._normalize_text(
                raw,
                name=f"{name}.{key}",
                maximum=300,
                required=False,
            )
        return normalized

    @classmethod
    def _assert_complete(cls, row: Mapping[str, Any]) -> None:
        missing: list[str] = []
        for key, label in (
            ("birth_date", "birth date"),
            ("nationality", "nationality"),
            ("phone_number", "phone number"),
            ("privacy_notice_version", "privacy notice"),
            ("privacy_acknowledged_at", "privacy acknowledgment"),
            ("client_signature_reference", "client signature"),
            ("client_signature_digest", "client signature digest"),
        ):
            value = row.get(key)
            if value is None or (isinstance(value, str) and not value.strip()):
                missing.append(label)
        for key, label in (
            ("present_address", "present address"),
            ("permanent_address", "permanent address"),
            ("livelihood_profile", "livelihood profile"),
        ):
            if not row.get(key):
                missing.append(label)
        if missing:
            raise CifInvalid(
                "The CIF is incomplete: " + ", ".join(missing) + "."
            )

    @staticmethod
    def _source_payload(row: Mapping[str, Any]) -> dict[str, object]:
        return {
            "legal_full_name": row["legal_full_name"],
            "birth_date": row["birth_date"],
            "place_of_birth": row["place_of_birth"],
            "nationality": row["nationality"],
            "civil_status": row["civil_status"],
            "phone_number": row["phone_number"],
            "email": row["email"],
            "present_address": row["present_address"],
            "permanent_address": row["permanent_address"],
            "same_as_present_address": row["same_as_present_address"],
            "livelihood_profile": row["livelihood_profile"],
            "privacy_notice_version": row["privacy_notice_version"],
            "privacy_acknowledged_at": row["privacy_acknowledged_at"],
            "client_signature_reference": row["client_signature_reference"],
            "client_signature_digest": (
                str(row["client_signature_digest"]).strip()
                if row["client_signature_digest"] is not None
                else None
            ),
            "form_schema_version": row["form_schema_version"],
        }

    @staticmethod
    def _audit(
        cursor,
        *,
        actor_user_id: UUID,
        action: str,
        target_type: str,
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
            ) values (%s, %s, %s, %s, %s)
            """,
            (actor_user_id, action, target_type, target_id, Jsonb(details)),
        )

    @staticmethod
    def _require_aware(value: datetime, *, name: str) -> None:
        if value.tzinfo is None or value.utcoffset() is None:
            raise CifInvalid(f"{name} must be timezone-aware.")
        value.astimezone(UTC)
