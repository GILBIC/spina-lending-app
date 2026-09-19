"""Immutable wet-sign evidence bound to a server-derived exact review snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from typing import Any
from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .database import open_connection
from .client_cif_identity_information import cif_information_from_row
from .office_review_evidence_storage import EvidenceFileError, PrivateEvidenceStore


class OfficeReviewEvidenceConflict(RuntimeError):
    pass


class OfficeReviewEvidenceAccessDenied(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class OfficeReviewEvidence:
    id: UUID
    request_id: UUID
    client_id: UUID
    cif_version_id: UUID
    application_id: UUID | None
    application_version_id: UUID | None
    purpose: str
    subject_id: UUID
    review_snapshot: dict[str, Any]
    snapshot_sha256: str
    content_sha256: str
    media_type: str
    byte_count: int
    captured_by_user_id: UUID
    captured_at: datetime

    @property
    def evidence_reference(self) -> str:
        return f"office-evidence:{self.id}"


def snapshot_digest(snapshot: dict[str, Any]) -> str:
    encoded = json.dumps(
        snapshot,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def cif_review_snapshot(
    *, client_id: UUID, cif_version_id: UUID, information: dict
) -> dict:
    return {
        "schema_version": 1,
        "scope": "cif_information_review",
        "client_id": str(client_id),
        "cif_version_id": str(cif_version_id),
        "information": information,
    }


def application_review_snapshot(
    *,
    client_id: UUID,
    cif_version_id: UUID,
    application_id: UUID,
    application_version_id: UUID,
    information: dict,
    cif_information: dict,
) -> dict:
    return {
        "schema_version": 1,
        "scope": "application_information_review",
        "client_id": str(client_id),
        "cif_version_id": str(cif_version_id),
        "application_id": str(application_id),
        "application_version_id": str(application_version_id),
        "information": information,
        "cif_information": cif_information,
    }


def evidence_id(reference: str) -> UUID:
    try:
        prefix, value = reference.strip().split(":", 1)
        if prefix != "office-evidence":
            raise ValueError
        return UUID(value)
    except (AttributeError, ValueError) as error:
        raise OfficeReviewEvidenceConflict(
            "Protected signed review evidence is required."
        ) from error


def _record(row) -> OfficeReviewEvidence:
    return OfficeReviewEvidence(
        **{name: row[name] for name in OfficeReviewEvidence.__dataclass_fields__}
    )


def capture_evidence(
    cursor,
    *,
    actor_user_id: UUID,
    client_id: UUID,
    cif_version_id: UUID,
    purpose: str,
    subject_id: UUID,
    review_snapshot: dict,
    content: bytes,
    media_type: str,
    request_id: UUID,
    application_id: UUID | None = None,
    application_version_id: UUID | None = None,
) -> OfficeReviewEvidence:
    """Caller authorizes and locks its domain source; this runs in that transaction.

    Private files are addressed by the retry UUID. A rollback can leave a private
    unreferenced file; an exact retry safely reuses it, never overwrites it.
    """
    digest = snapshot_digest(review_snapshot)
    content_hash = hashlib.sha256(content).hexdigest()
    values = {
        "request_id": request_id,
        "client_id": client_id,
        "cif_version_id": cif_version_id,
        "application_id": application_id,
        "application_version_id": application_version_id,
        "purpose": purpose,
        "subject_id": subject_id,
        "review_snapshot": review_snapshot,
        "snapshot_sha256": digest,
        "content_sha256": content_hash,
        "media_type": media_type,
        "byte_count": len(content),
        "captured_by_user_id": actor_user_id,
    }
    # Serialize retries before touching the file, including concurrent first uploads.
    cursor.execute(
        "select pg_advisory_xact_lock(hashtextextended(%s, 0))", (str(request_id),)
    )
    existing = cursor.execute(
        "select * from lending.office_review_evidence where request_id = %s",
        (request_id,),
    ).fetchone()
    if existing is not None:
        if any(existing[name] != value for name, value in values.items()):
            raise OfficeReviewEvidenceConflict(
                "Evidence retry does not match its original capture."
            )
        record = _record(existing)
        PrivateEvidenceStore().read(
            record.request_id, record.content_sha256, record.byte_count
        )
        return record
    PrivateEvidenceStore().put(request_id, content, media_type)
    values["review_snapshot"] = Jsonb(review_snapshot)
    row = cursor.execute(
        """
        insert into lending.office_review_evidence (
            request_id, client_id, cif_version_id, application_id, application_version_id,
            purpose, subject_id, review_snapshot, snapshot_sha256, content_sha256,
            media_type, byte_count, captured_by_user_id
        ) values (
            %(request_id)s, %(client_id)s, %(cif_version_id)s, %(application_id)s,
            %(application_version_id)s, %(purpose)s, %(subject_id)s, %(review_snapshot)s,
            %(snapshot_sha256)s, %(content_sha256)s, %(media_type)s, %(byte_count)s,
            %(captured_by_user_id)s
        ) returning *
        """,
        values,
    ).fetchone()
    return _record(row)


def require_evidence(
    cursor,
    *,
    evidence_reference: str,
    actor_user_id: UUID,
    client_id: UUID,
    purpose: str,
    subject_id: UUID,
    review_snapshot: dict,
) -> OfficeReviewEvidence:
    row = cursor.execute(
        "select * from lending.office_review_evidence where id = %s",
        (evidence_id(evidence_reference),),
    ).fetchone()
    if row is None or any(
        (
            row["client_id"] != client_id,
            row["purpose"] != purpose,
            row["subject_id"] != subject_id,
            row["captured_by_user_id"] != actor_user_id,
            row["review_snapshot"] != review_snapshot,
            row["snapshot_sha256"] != snapshot_digest(review_snapshot),
        )
    ):
        raise OfficeReviewEvidenceConflict(
            "Signed evidence does not match this exact review and witness."
        )
    record = _record(row)
    try:
        PrivateEvidenceStore().read(
            record.request_id, record.content_sha256, record.byte_count
        )
    except EvidenceFileError as error:
        raise OfficeReviewEvidenceConflict(
            "Signed evidence is unavailable or failed its integrity check."
        ) from error
    return record


def _require_actor(cursor, actor_user_id: UUID) -> None:
    allowed = cursor.execute(
        """
        select 1 from core.users actor
        where actor.id = %s and actor.status = 'active'
          and exists (
            select 1 from core.user_roles assigned
            join core.roles role on role.id = assigned.role_id
            join core.role_permissions permission on permission.role_id = role.id
            where assigned.user_id = actor.id and role.code in ('employee', 'management')
              and permission.permission_code = 'client_onboarding.requirement.review'
          )
        """,
        (actor_user_id,),
    ).fetchone()
    if allowed is None:
        raise OfficeReviewEvidenceAccessDenied(
            "An active authorized office account is required."
        )


def load_review_context(
    cursor,
    *,
    client_id: UUID,
    cif_version_id: UUID,
    purpose: str,
    application_id: UUID | None = None,
    application_version_id: UUID | None = None,
    lock: bool = False,
    optional_service_communications: bool = False,
) -> dict:
    if purpose == "privacy_acknowledgment":
        from .privacy_record_repository import build_privacy_context

        return build_privacy_context(
            cursor,
            client_id=client_id,
            cif_version_id=cif_version_id,
            optional_service_communications=optional_service_communications,
            lock=lock,
        )
    if optional_service_communications:
        raise OfficeReviewEvidenceConflict(
            "Optional privacy consent belongs to its separate acknowledgment."
        )
    from .client_cif_repository import normalize_cif_information
    from .loan_application_information import parse_loan_application_information

    version = None
    if purpose == "application_review":
        version = cursor.execute(
            """
            select version.* from lending.loan_application_versions version
            join lending.loan_applications application
              on application.id = version.application_id and application.client_id = version.client_id
            where version.id = %s and version.application_id = %s
              and version.client_id = %s and version.cif_version_id = %s
              and version.version_number = (
                select max(latest.version_number) from lending.loan_application_versions latest
                where latest.application_id = version.application_id
              )
            """
            + (" for update of application" if lock else ""),
            (application_version_id, application_id, client_id, cif_version_id),
        ).fetchone()
        if version is None:
            raise OfficeReviewEvidenceConflict(
                "The exact latest application review is unavailable."
            )
    elif (
        purpose != "cif_review"
        or application_id is not None
        or application_version_id is not None
    ):
        raise OfficeReviewEvidenceConflict("Invalid review evidence source.")
    cif = cursor.execute(
        """
        select cif.*, client.status as client_status
        from lending.client_cif_versions cif
        join lending.clients client on client.id = cif.client_id
        join lending.client_onboarding_applicants applicant on applicant.promoted_client_id = cif.client_id
        where cif.id = %s and cif.client_id = %s and cif.is_current = true
          and ((cif.status = 'active' and client.status = 'active')
            or (cif.status = 'draft' and (client.status = 'inactive' or (
              client.status = 'active' and exists (
                select 1 from lending.client_cif_review_cycles cycle where cycle.cif_version_id = cif.id
              )))))
          and applicant.status = 'eligible_for_cif'
        """
        + (" for update of cif, client, applicant" if lock else ""),
        (cif_version_id, client_id),
    ).fetchone()
    if cif is None:
        raise OfficeReviewEvidenceConflict(
            "The exact current CIF review is unavailable."
        )
    information = cif_information_from_row(cif)
    try:
        normalize_cif_information(information)
    except ValueError as error:
        raise OfficeReviewEvidenceConflict(
            "CIF information is incomplete or invalid."
        ) from error
    if version is None:
        snapshot = cif_review_snapshot(
            client_id=client_id, cif_version_id=cif_version_id, information=information
        )
        subject_id = cif_version_id
    else:
        application_information = parse_loan_application_information(
            version["information"]
        )
        if application_information.missing_fields():
            raise OfficeReviewEvidenceConflict("Application information is incomplete.")
        confirmation = cursor.execute(
            "select review_snapshot, applicant_confirmation_evidence_reference, witnessed_by_user_id "
            "from lending.client_cif_review_confirmations where client_id = %s and cif_version_id = %s",
            (client_id, cif_version_id),
        ).fetchone()
        if confirmation is None or confirmation["review_snapshot"] != information:
            raise OfficeReviewEvidenceConflict(
                "Exact CIF review confirmation is required."
            )
        require_evidence(
            cursor,
            evidence_reference=confirmation[
                "applicant_confirmation_evidence_reference"
            ],
            actor_user_id=confirmation["witnessed_by_user_id"],
            client_id=client_id,
            purpose="cif_review",
            subject_id=cif_version_id,
            review_snapshot=cif_review_snapshot(
                client_id=client_id,
                cif_version_id=cif_version_id,
                information=information,
            ),
        )
        snapshot = application_review_snapshot(
            client_id=client_id,
            cif_version_id=cif_version_id,
            application_id=application_id,
            application_version_id=application_version_id,
            information=application_information.model_dump(mode="json"),
            cif_information=information,
        )
        subject_id = application_version_id
    return {
        "client_id": str(client_id),
        "cif_version_id": str(cif_version_id),
        "application_id": None if application_id is None else str(application_id),
        "application_version_id": None
        if application_version_id is None
        else str(application_version_id),
        "purpose": purpose,
        "subject_id": str(subject_id),
        "review_snapshot": snapshot,
        "snapshot_sha256": snapshot_digest(snapshot),
    }


class PostgresOfficeReviewEvidenceRepository:
    def get_context(self, *, actor_user_id: UUID, **source) -> dict:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                _require_actor(cursor, actor_user_id)
                return load_review_context(cursor, **source)

    def capture(
        self,
        *,
        actor_user_id: UUID,
        expected_snapshot_sha256: str,
        request_id: UUID,
        content: bytes,
        media_type: str,
        **source,
    ) -> OfficeReviewEvidence:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                _require_actor(cursor, actor_user_id)
                context = load_review_context(cursor, lock=True, **source)
                if context.get("issuance_ready") is False:
                    raise OfficeReviewEvidenceConflict(
                        "The controlled document is not ready for signed evidence capture."
                    )
                if context["snapshot_sha256"] != expected_snapshot_sha256:
                    raise OfficeReviewEvidenceConflict(
                        "Review changed; refresh before capturing signed evidence."
                    )
                return capture_evidence(
                    cursor,
                    actor_user_id=actor_user_id,
                    **{
                        key: source.get(key)
                        for key in (
                            "client_id",
                            "cif_version_id",
                            "purpose",
                            "application_id",
                            "application_version_id",
                        )
                    },
                    subject_id=UUID(context["subject_id"]),
                    review_snapshot=context["review_snapshot"],
                    content=content,
                    media_type=media_type,
                    request_id=request_id,
                )

    def get_content(self, *, actor_user_id: UUID, client_id: UUID, record_id: UUID):
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                _require_actor(cursor, actor_user_id)
                row = cursor.execute(
                    "select * from lending.office_review_evidence where id = %s and client_id = %s",
                    (record_id, client_id),
                ).fetchone()
                if row is None:
                    raise OfficeReviewEvidenceConflict(
                        "Signed review evidence is unavailable."
                    )
                record = _record(row)
                return record, PrivateEvidenceStore().read(
                    record.request_id, record.content_sha256, record.byte_count
                )
