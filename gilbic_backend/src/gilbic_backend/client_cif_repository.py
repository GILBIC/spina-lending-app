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
