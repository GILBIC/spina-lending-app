from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast
from uuid import UUID

from psycopg.rows import dict_row

from .database import open_connection


ClientCifStatus = Literal["draft", "active", "superseded"]
ClientCifLivenessStatus = Literal["pending", "passed", "failed"]


@dataclass(frozen=True, slots=True)
class ClientCifVersion:
    id: UUID
    client_id: UUID
    version_number: int
    is_current: bool
    status: ClientCifStatus
    full_name: str
    phone_number: str
    email: str | None
    present_address: str
    national_id_egov_evidence_reference: str | None
    tin_id_egov_evidence_reference: str | None
    meralco_bill_evidence_reference: str | None
    baseline_face_scan_evidence_reference: str | None
    baseline_liveness_status: ClientCifLivenessStatus
    activated_at: datetime | None
    expires_at: datetime | None
    review_due_at: datetime | None
    reverification_required_at: datetime | None
    reverification_reason: str | None


class ClientCifConflict(RuntimeError):
    """Raised when CIF work is not valid for the requested Client state."""


def _optional_text(value: object) -> str | None:
    return None if value is None else str(value)


def _record_from_row(row: Mapping[str, object]) -> ClientCifVersion:
    return ClientCifVersion(
        id=cast(UUID, row["id"]),
        client_id=cast(UUID, row["client_id"]),
        version_number=int(cast(int, row["version_number"])),
        is_current=bool(row["is_current"]),
        status=cast(ClientCifStatus, str(row["status"])),
        full_name=str(row["full_name"]),
        phone_number=str(row["phone_number"]),
        email=_optional_text(row["email"]),
        present_address=str(row["present_address"]),
        national_id_egov_evidence_reference=_optional_text(
            row["national_id_egov_evidence_reference"]
        ),
        tin_id_egov_evidence_reference=_optional_text(
            row["tin_id_egov_evidence_reference"]
        ),
        meralco_bill_evidence_reference=_optional_text(
            row["meralco_bill_evidence_reference"]
        ),
        baseline_face_scan_evidence_reference=_optional_text(
            row["baseline_face_scan_evidence_reference"]
        ),
        baseline_liveness_status=cast(
            ClientCifLivenessStatus,
            str(row["baseline_liveness_status"]),
        ),
        activated_at=cast(datetime | None, row["activated_at"]),
        expires_at=cast(datetime | None, row["expires_at"]),
        review_due_at=cast(datetime | None, row["review_due_at"]),
        reverification_required_at=cast(
            datetime | None,
            row["reverification_required_at"],
        ),
        reverification_reason=_optional_text(row["reverification_reason"]),
    )


_CIF_RETURNING_COLUMNS = """
    id,
    client_id,
    version_number,
    is_current,
    status,
    full_name,
    phone_number,
    email,
    present_address,
    national_id_egov_evidence_reference,
    tin_id_egov_evidence_reference,
    meralco_bill_evidence_reference,
    baseline_face_scan_evidence_reference,
    baseline_liveness_status,
    activated_at,
    expires_at,
    review_due_at,
    reverification_required_at,
    reverification_reason
"""

_CIF_SELECT_COLUMNS = """
    cif.id,
    cif.client_id,
    cif.version_number,
    cif.is_current,
    cif.status,
    cif.full_name,
    cif.phone_number,
    cif.email,
    cif.present_address,
    cif.national_id_egov_evidence_reference,
    cif.tin_id_egov_evidence_reference,
    cif.meralco_bill_evidence_reference,
    cif.baseline_face_scan_evidence_reference,
    cif.baseline_liveness_status,
    cif.activated_at,
    cif.expires_at,
    cif.review_due_at,
    cif.reverification_required_at,
    cif.reverification_reason
"""


class PostgresClientCifRepository:
    def begin_draft(
        self,
        *,
        actor_user_id: UUID,
        client_id: UUID,
    ) -> ClientCifVersion:
        """Begin the first CIF draft only from an eligible promoted Client."""

        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select
                        applicant.id as applicant_id,
                        applicant.promoted_client_id as client_id,
                        client.status as client_status,
                        applicant.full_name,
                        applicant.phone_number,
                        applicant.email,
                        applicant.present_address,
                        applicant.national_id_egov_evidence_reference,
                        applicant.tin_id_egov_evidence_reference,
                        applicant.meralco_bill_evidence_reference
                    from lending.client_onboarding_applicants applicant
                    join lending.clients client on client.id = applicant.promoted_client_id
                    where applicant.promoted_client_id = %s
                      and applicant.status = 'eligible_for_cif'
                      and client.status = 'inactive'
                    for update
                    """,
                    (client_id,),
                )
                source = cursor.fetchone()
                if source is None:
                    raise ClientCifConflict(
                        "CIF work requires an eligible promoted inactive Client."
                    )

                cursor.execute(
                    f"""
                    select {_CIF_RETURNING_COLUMNS}
                    from lending.client_cif_versions
                    where client_id = %s
                      and is_current = true
                      and status = 'draft'
                    limit 1
                    for update
                    """,
                    (client_id,),
                )
                existing = cursor.fetchone()
                if existing is not None:
                    return _record_from_row(existing)

                cursor.execute(
                    f"""
                    insert into lending.client_cif_versions (
                        client_id,
                        version_number,
                        is_current,
                        status,
                        full_name,
                        phone_number,
                        email,
                        present_address,
                        national_id_egov_evidence_reference,
                        tin_id_egov_evidence_reference,
                        meralco_bill_evidence_reference,
                        created_by_user_id
                    )
                    values (
                        %s,
                        1,
                        true,
                        'draft',
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    returning {_CIF_RETURNING_COLUMNS}
                    """,
                    (
                        client_id,
                        source["full_name"],
                        source["phone_number"],
                        source["email"],
                        source["present_address"],
                        source["national_id_egov_evidence_reference"],
                        source["tin_id_egov_evidence_reference"],
                        source["meralco_bill_evidence_reference"],
                        actor_user_id,
                    ),
                )
                created = cursor.fetchone()
                if created is None:
                    raise RuntimeError("Unable to create Client CIF draft.")
                return _record_from_row(created)

    def record_baseline_live_face(
        self,
        *,
        client_id: UUID,
        evidence_reference: str,
        liveness_status: ClientCifLivenessStatus,
    ) -> ClientCifVersion:
        """Record controlled baseline face/liveness evidence on the current draft."""

        normalized_reference = evidence_reference.strip()
        if not normalized_reference:
            raise ValueError("Baseline face evidence reference is required.")
        normalized_status = str(liveness_status).strip().lower()
        if normalized_status not in {"pending", "passed", "failed"}:
            raise ValueError("Baseline liveness status is invalid.")

        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    update lending.client_cif_versions
                    set
                        baseline_face_scan_evidence_reference = %s,
                        baseline_liveness_status = %s,
                        updated_at = now()
                    where client_id = %s
                      and is_current = true
                      and status = 'draft'
                    returning {_CIF_RETURNING_COLUMNS}
                    """,
                    (normalized_reference, normalized_status, client_id),
                )
                updated = cursor.fetchone()
                if updated is None:
                    raise ClientCifConflict(
                        "Baseline live-face evidence requires the current CIF draft."
                    )
                return _record_from_row(updated)

    def activate_current(
        self,
        *,
        actor_user_id: UUID,
        client_id: UUID,
    ) -> ClientCifVersion:
        """Activate a ready current CIF and the existing Client exactly once."""

        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    select {_CIF_SELECT_COLUMNS}
                    from lending.client_cif_versions cif
                    join lending.client_onboarding_applicants applicant
                      on applicant.promoted_client_id = cif.client_id
                    join lending.clients client
                      on client.id = cif.client_id
                    where cif.client_id = %s
                      and cif.is_current = true
                      and cif.status in ('draft', 'active')
                      and applicant.status = 'eligible_for_cif'
                      and (
                            (cif.status = 'draft' and client.status = 'inactive')
                            or (cif.status = 'active' and client.status = 'active')
                      )
                    limit 1
                    for update of cif, applicant, client
                    """,
                    (client_id,),
                )
                current = cursor.fetchone()
                if current is None:
                    raise ClientCifConflict(
                        "CIF activation requires the authoritative eligible Client link."
                    )

                if str(current["status"]) == "active":
                    return _record_from_row(current)

                face_reference = _optional_text(
                    current["baseline_face_scan_evidence_reference"]
                )
                if (
                    str(current["baseline_liveness_status"]) != "passed"
                    or face_reference is None
                    or not face_reference.strip()
                ):
                    raise ClientCifConflict(
                        "CIF activation requires passed liveness and baseline face evidence."
                    )

                cursor.execute(
                    f"""
                    update lending.client_cif_versions
                    set
                        status = 'active',
                        activated_at = now(),
                        expires_at = now() + interval '5 years',
                        review_due_at = now() + interval '5 years' - interval '90 days',
                        activated_by_user_id = %s,
                        updated_at = now()
                    where client_id = %s
                      and is_current = true
                      and status = 'draft'
                    returning {_CIF_RETURNING_COLUMNS}
                    """,
                    (actor_user_id, client_id),
                )
                activated = cursor.fetchone()
                if activated is None:
                    raise ClientCifConflict("The current CIF could not be activated.")

                cursor.execute(
                    """
                    update lending.clients
                    set status = 'active', updated_at = now()
                    where id = %s
                      and status = 'inactive'
                    """,
                    (client_id,),
                )
                return _record_from_row(activated)
