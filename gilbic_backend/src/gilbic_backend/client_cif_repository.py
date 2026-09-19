from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Literal, cast
from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .database import open_connection
from .client_cif_identity_information import (
    CifIdentityInformation,
    cif_information_from_row,
)
from .office_review_evidence_repository import (
    OfficeReviewEvidenceAccessDenied,
    OfficeReviewEvidenceConflict,
    _require_actor as _require_review_actor,
    cif_review_snapshot,
    require_evidence,
)


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


@dataclass(frozen=True, slots=True)
class ClientCifCorrectionSummary(ClientCifVersion):
    can_correct_information: bool


@dataclass(frozen=True, slots=True)
class ClientCifIdentitySummary(ClientCifVersion):
    identity_information: dict | None
    can_correct_information: bool = False


@dataclass(frozen=True, slots=True)
class ClientCifReviewConfirmationRecord:
    id: UUID
    client_id: UUID
    cif_version_id: UUID
    review_cycle_number: int
    review_snapshot: dict[str, object]
    applicant_confirmation_evidence_reference: str
    witnessed_by_user_id: UUID
    confirmed_at: datetime


class ClientCifConflict(RuntimeError):
    """Raised when CIF work is not valid for the requested Client state."""


class ClientCifAccessDenied(RuntimeError):
    """Raised when the persisted actor cannot perform protected CIF work."""


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


def _confirmation_record_from_row(
    row: Mapping[str, object],
) -> ClientCifReviewConfirmationRecord:
    return ClientCifReviewConfirmationRecord(
        id=cast(UUID, row["id"]),
        client_id=cast(UUID, row["client_id"]),
        cif_version_id=cast(UUID, row["cif_version_id"]),
        review_cycle_number=int(cast(int, row["review_cycle_number"])),
        review_snapshot=_cif_information_snapshot(
            cast(Mapping[str, object], row["review_snapshot"])
        ),
        applicant_confirmation_evidence_reference=str(
            row["applicant_confirmation_evidence_reference"]
        ),
        witnessed_by_user_id=cast(UUID, row["witnessed_by_user_id"]),
        confirmed_at=cast(datetime, row["confirmed_at"]),
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


_CIF_INFORMATION_FIELDS = ("full_name", "phone_number", "email", "present_address")


def _cif_information_snapshot(value: Mapping[str, object]) -> dict:
    if not isinstance(value, Mapping) or set(value) not in (
        set(_CIF_INFORMATION_FIELDS),
        {*_CIF_INFORMATION_FIELDS, "identity_information"},
    ):
        raise ValueError(
            "The four CIF fields and optional identity information are required."
        )
    for field in _CIF_INFORMATION_FIELDS:
        if not isinstance(value[field], str) and not (
            field == "email" and value[field] is None
        ):
            raise ValueError(
                "CIF information fields must be text; only email may be null."
            )
    # Never normalize the reviewed snapshot: it must match the stored values exactly.
    result = {field: value[field] for field in _CIF_INFORMATION_FIELDS}
    if value.get("identity_information") is not None:
        CifIdentityInformation.model_validate(value["identity_information"])
        result["identity_information"] = dict(value["identity_information"])
    return result


def normalize_cif_information(value: Mapping[str, object]) -> dict[str, str | None]:
    """Validate new information using the existing office-intake text conventions."""

    information = _cif_information_snapshot(value)
    limits = {
        "full_name": (2, 200),
        "phone_number": (7, 40),
        "present_address": (5, 500),
    }
    for field, (minimum, maximum) in limits.items():
        raw = cast(str, information[field])
        normalized = (
            "".join(character for character in raw if character.isdigit())
            if field == "phone_number"
            else " ".join(raw.split())
        )
        if len(raw) > maximum or not minimum <= len(normalized) <= maximum:
            raise ValueError(f"Invalid CIF {field.replace('_', ' ')}.")
        information[field] = normalized
    email = information["email"]
    if email is not None:
        if len(email) > 320:
            raise ValueError("CIF email is too long.")
        information["email"] = email.strip().lower() or None
    if information.get("identity_information") is not None:
        information["identity_information"] = CifIdentityInformation.model_validate(
            information["identity_information"]
        ).model_dump(mode="json")
    return information


def _review_record_from_row(row):
    record = _record_from_row(row)
    if row.get("identity_information") is not None:
        return ClientCifIdentitySummary(
            **asdict(record), identity_information=row["identity_information"]
        )
    return record


class PostgresClientCifRepository:
    def begin_review_cycle(
        self,
        *,
        actor_user_id: UUID,
        client_id: UUID,
        cif_version_id: UUID,
        expected_information: Mapping[str, object],
        corrected_information: Mapping[str, object],
        reason: str,
    ) -> ClientCifVersion:
        expected = _cif_information_snapshot(expected_information)
        corrected = normalize_cif_information(corrected_information)
        reason = " ".join(reason.split())
        if not 3 <= len(reason) <= 500:
            raise ValueError(
                "A review-cycle reason of 3 to 500 characters is required."
            )
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                try:
                    _require_review_actor(cursor, actor_user_id)
                except OfficeReviewEvidenceAccessDenied as error:
                    raise ClientCifAccessDenied(str(error)) from error
                current = cursor.execute(
                    f"""
                    select {_CIF_SELECT_COLUMNS}, cif.identity_information, client.status as client_status,
                           applicant.status as applicant_status,
                           exists (select 1 from lending.client_cif_review_cycles cycle
                                   where cycle.cif_version_id = cif.id) as is_successor
                    from lending.client_cif_versions cif
                    join lending.clients client on client.id = cif.client_id
                    join lending.client_onboarding_applicants applicant
                      on applicant.promoted_client_id = cif.client_id
                    where cif.id = %s and cif.client_id = %s
                    for update of cif, client, applicant
                    """,
                    (cif_version_id, client_id),
                ).fetchone()
                if current is None:
                    raise ClientCifConflict(
                        "No eligible CIF review cycle is available."
                    )
                previous = cursor.execute(
                    f"""
                    select {_CIF_SELECT_COLUMNS}, cif.identity_information, cycle.reason, cycle.created_by_user_id
                    from lending.client_cif_review_cycles cycle
                    join lending.client_cif_versions cif on cif.id = cycle.cif_version_id
                    where cycle.predecessor_cif_version_id = %s and cycle.client_id = %s
                    """,
                    (cif_version_id, client_id),
                ).fetchone()
                saved = cif_information_from_row(current)
                if saved != expected:
                    raise ClientCifConflict("CIF changed; refresh the office review.")
                if previous is not None:
                    if (
                        previous["reason"] != reason
                        or previous["created_by_user_id"] != actor_user_id
                        or cif_information_from_row(previous) != corrected
                    ):
                        raise ClientCifConflict(
                            "Review cycle was already started with different information."
                        )
                    return _review_record_from_row(previous)
                if not (
                    current["is_current"]
                    and (
                        (
                            current["status"] == "active"
                            and current["client_status"] == "active"
                        )
                        or (
                            current["status"] == "draft"
                            and (
                                current["client_status"] == "inactive"
                                or (
                                    current["client_status"] == "active"
                                    and current["is_successor"]
                                )
                            )
                        )
                    )
                    and current["applicant_status"] == "eligible_for_cif"
                ):
                    raise ClientCifConflict(
                        "No eligible CIF review cycle is available."
                    )
                confirmed = cursor.execute(
                    "select 1 from lending.client_cif_review_confirmations where cif_version_id = %s",
                    (cif_version_id,),
                ).fetchone()
                if confirmed is None and current["status"] != "active":
                    raise ClientCifConflict(
                        "Correct the unconfirmed draft before starting another review cycle."
                    )
                number = cursor.execute(
                    "select coalesce(max(version_number), 0) + 1 as next_version "
                    "from lending.client_cif_versions where client_id = %s",
                    (client_id,),
                ).fetchone()["next_version"]
                # Retain historical information, activation dates and verification
                # evidence. Existing Client servicing remains active throughout.
                cursor.execute(
                    "update lending.client_cif_versions set is_current = false where id = %s",
                    (cif_version_id,),
                )
                created = cursor.execute(
                    f"""
                    insert into lending.client_cif_versions (
                        client_id, version_number, full_name, phone_number, email, present_address,
                        national_id_egov_evidence_reference, tin_id_egov_evidence_reference,
                        meralco_bill_evidence_reference, created_by_user_id, identity_information
                    ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    returning {_CIF_RETURNING_COLUMNS}, identity_information
                    """,
                    (
                        client_id,
                        number,
                        corrected["full_name"],
                        corrected["phone_number"],
                        corrected["email"],
                        corrected["present_address"],
                        current["national_id_egov_evidence_reference"],
                        current["tin_id_egov_evidence_reference"],
                        current["meralco_bill_evidence_reference"],
                        actor_user_id,
                        Jsonb(corrected["identity_information"])
                        if "identity_information" in corrected
                        else None,
                    ),
                ).fetchone()
                cursor.execute(
                    "insert into lending.client_cif_review_cycles "
                    "(cif_version_id, client_id, predecessor_cif_version_id, reason, created_by_user_id) "
                    "values (%s, %s, %s, %s, %s)",
                    (created["id"], client_id, cif_version_id, reason, actor_user_id),
                )
                return _review_record_from_row(created)

    def confirm_review(
        self,
        *,
        actor_user_id: UUID,
        client_id: UUID,
        cif_version_id: UUID,
        expected_information: Mapping[str, object],
        applicant_confirmation_evidence_reference: str,
    ) -> ClientCifReviewConfirmationRecord:
        expected = _cif_information_snapshot(expected_information)
        if not isinstance(applicant_confirmation_evidence_reference, str):
            raise ValueError("Applicant confirmation evidence reference is required.")
        evidence_reference = applicant_confirmation_evidence_reference.strip()
        if not evidence_reference:
            raise ValueError("Applicant confirmation evidence reference is required.")

        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                allowed = cursor.execute(
                    """
                    select 1
                    from core.users user_account
                    where user_account.id = %s
                      and user_account.status = 'active'
                      and exists (
                          select 1
                          from core.user_roles user_role
                          join core.roles role on role.id = user_role.role_id
                          join core.role_permissions permission
                            on permission.role_id = role.id
                          where user_role.user_id = user_account.id
                            and role.code in ('employee', 'management')
                            and permission.permission_code = %s
                      )
                    """,
                    (actor_user_id, "client_onboarding.requirement.review"),
                ).fetchone()
                if allowed is None:
                    raise ClientCifAccessDenied(
                        "An active authorized office account is required."
                    )

                current = cursor.execute(
                    f"""
                    select {_CIF_SELECT_COLUMNS}, cif.identity_information,
                           applicant.status as applicant_status,
                           client.status as client_status,
                           exists (select 1 from lending.client_cif_review_cycles cycle
                                   where cycle.cif_version_id = cif.id) as is_successor
                    from lending.client_cif_versions cif
                    join lending.client_onboarding_applicants applicant
                      on applicant.promoted_client_id = cif.client_id
                    join lending.clients client on client.id = cif.client_id
                    where cif.id = %s and cif.client_id = %s
                    for update of cif, applicant, client
                    """,
                    (cif_version_id, client_id),
                ).fetchone()
                existing = cursor.execute(
                    """
                    select id, client_id, cif_version_id, review_cycle_number,
                           review_snapshot,
                           applicant_confirmation_evidence_reference,
                           witnessed_by_user_id, confirmed_at
                    from lending.client_cif_review_confirmations
                    where cif_version_id = %s
                    """,
                    (cif_version_id,),
                ).fetchone()

                def verify_evidence():
                    try:
                        require_evidence(
                            cursor,
                            evidence_reference=evidence_reference,
                            actor_user_id=actor_user_id,
                            client_id=client_id,
                            purpose="cif_review",
                            subject_id=cif_version_id,
                            review_snapshot=cif_review_snapshot(
                                client_id=client_id,
                                cif_version_id=cif_version_id,
                                information=expected,
                            ),
                        )
                    except OfficeReviewEvidenceConflict as error:
                        raise ClientCifConflict(str(error)) from error

                if existing is not None:
                    if (
                        existing["client_id"] != client_id
                        or existing["review_snapshot"] != expected
                        or existing["applicant_confirmation_evidence_reference"]
                        != evidence_reference
                        or existing["witnessed_by_user_id"] != actor_user_id
                    ):
                        raise ClientCifConflict(
                            "CIF version was already confirmed with different review evidence or witness."
                        )
                    verify_evidence()
                    return _confirmation_record_from_row(existing)

                if current is None:
                    raise ClientCifConflict("No eligible current CIF is available.")
                if not (
                    bool(current["is_current"])
                    and str(current["applicant_status"]) == "eligible_for_cif"
                    and (
                        (
                            str(current["status"]) == "draft"
                            and (
                                str(current["client_status"]) == "inactive"
                                or (
                                    str(current["client_status"]) == "active"
                                    and current["is_successor"]
                                )
                            )
                        )
                        or (
                            str(current["status"]) == "active"
                            and str(current["client_status"]) == "active"
                        )
                    )
                ):
                    raise ClientCifConflict("No eligible current CIF is available.")

                saved = cif_information_from_row(current)
                try:
                    normalize_cif_information(saved)
                except ValueError as error:
                    raise ClientCifConflict(
                        "CIF information is incomplete or invalid and cannot be confirmed."
                    ) from error
                if saved != expected:
                    raise ClientCifConflict("CIF changed; refresh the office review.")
                verify_evidence()

                cycle = cursor.execute(
                    """
                    select coalesce(max(review_cycle_number), 0) + 1 as next_cycle
                    from lending.client_cif_review_confirmations
                    where client_id = %s
                    """,
                    (client_id,),
                ).fetchone()
                created = cursor.execute(
                    """
                    insert into lending.client_cif_review_confirmations (
                        client_id, cif_version_id, review_cycle_number,
                        review_snapshot,
                        applicant_confirmation_evidence_reference,
                        witnessed_by_user_id
                    ) values (%s, %s, %s, %s, %s, %s)
                    returning id, client_id, cif_version_id, review_cycle_number,
                              review_snapshot,
                              applicant_confirmation_evidence_reference,
                              witnessed_by_user_id, confirmed_at
                    """,
                    (
                        client_id,
                        cif_version_id,
                        cycle["next_cycle"],
                        Jsonb(saved),
                        evidence_reference,
                        actor_user_id,
                    ),
                ).fetchone()
                if created is None:
                    raise ClientCifConflict(
                        "CIF review confirmation was not readable after creation."
                    )
                return _confirmation_record_from_row(created)

    def get_review_summary(
        self,
        *,
        client_id: UUID,
        include_correction_availability: bool = False,
        include_identity_information: bool = False,
    ) -> ClientCifVersion:
        """Read the current eligible CIF without creating or changing any state."""

        columns = _CIF_SELECT_COLUMNS
        if include_identity_information:
            columns += ", cif.identity_information"
        if include_correction_availability:
            columns += """,
                (cif.status = 'draft' and (client.status = 'inactive' or (
                    client.status = 'active' and exists (
                        select 1 from lending.client_cif_review_cycles cycle where cycle.cif_version_id = cif.id
                    )))
                 and not exists (
                    select 1 from lending.client_cif_review_confirmations confirmation
                    where confirmation.client_id = cif.client_id
                      and confirmation.cif_version_id = cif.id
                 )) as can_correct_information
            """

        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    select {columns}
                    from lending.client_cif_versions cif
                    join lending.client_onboarding_applicants applicant
                      on applicant.promoted_client_id = cif.client_id
                    join lending.clients client
                      on client.id = cif.client_id
                    where cif.client_id = %s
                      and cif.is_current = true
                      and cif.status in ('draft', 'active')
                      and client.status in ('inactive', 'active')
                      and applicant.status = 'eligible_for_cif'
                    limit 1
                    """,
                    (client_id,),
                )
                current = cursor.fetchone()
                if current is None:
                    raise ClientCifConflict("No eligible current CIF is available.")
                record = _record_from_row(current)
                if include_identity_information:
                    return ClientCifIdentitySummary(
                        **asdict(record),
                        identity_information=current["identity_information"],
                        can_correct_information=current.get("can_correct_information")
                        is True,
                    )
                if include_correction_availability:
                    return ClientCifCorrectionSummary(
                        **asdict(record),
                        can_correct_information=current["can_correct_information"]
                        is True,
                    )
                return record

    def get_active_source_for_new_loan(
        self, *, client_id: UUID, cif_version_id: UUID
    ) -> ClientCifVersion:
        """Read one exact valid CIF as a new-loan prerequisite, not approval.

        Final approval must revalidate sources in its own transaction. Historical
        documents use their retained snapshots, not this current-CIF selector.
        """

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
                      and cif.id = %s
                      and cif.is_current = true
                      and cif.status = 'active'
                      and client.status = 'active'
                      and applicant.status = 'eligible_for_cif'
                      and cif.activated_at <= now()
                      and cif.expires_at > now()
                      and cif.reverification_required_at is null
                      and cif.baseline_liveness_status = 'passed'
                      and btrim(coalesce(cif.baseline_face_scan_evidence_reference, '')) <> ''
                    limit 1
                    """,
                    (client_id, cif_version_id),
                )
                current = cursor.fetchone()
                if current is None:
                    raise ClientCifConflict(
                        "No eligible active CIF is available for this new loan."
                    )
                return _record_from_row(current)

    def correct_draft_information(
        self,
        *,
        actor_user_id: UUID,
        client_id: UUID,
        cif_version_id: UUID,
        expected_information: Mapping[str, object],
        corrected_information: Mapping[str, object],
        reason: str,
    ) -> ClientCifVersion:
        """Correct an unconfirmed current draft and audit in one transaction."""

        expected = _cif_information_snapshot(expected_information)
        corrected = normalize_cif_information(corrected_information)
        if not isinstance(reason, str):
            raise ValueError("A CIF correction reason is required.")
        normalized_reason = " ".join(reason.split())
        if len(reason) > 500 or not 3 <= len(normalized_reason) <= 500:
            raise ValueError(
                "A CIF correction reason of 3 to 500 characters is required."
            )

        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    select {_CIF_SELECT_COLUMNS}, cif.identity_information
                    from lending.client_cif_versions cif
                    join lending.client_onboarding_applicants applicant
                      on applicant.promoted_client_id = cif.client_id
                    join lending.clients client
                      on client.id = cif.client_id
                    where cif.client_id = %s
                      and cif.id = %s
                      and cif.is_current = true
                      and cif.status = 'draft'
                      and (client.status = 'inactive' or (
                          client.status = 'active' and exists (
                              select 1 from lending.client_cif_review_cycles cycle where cycle.cif_version_id = cif.id
                          )))
                      and applicant.status = 'eligible_for_cif'
                    for update of cif, applicant, client
                    """,
                    (client_id, cif_version_id),
                )
                current = cursor.fetchone()
                if current is None:
                    raise ClientCifConflict(
                        "No eligible current CIF draft is available."
                    )
                cursor.execute(
                    """
                    select id from lending.client_cif_review_confirmations
                    where client_id = %s and cif_version_id = %s
                    limit 1
                    """,
                    (client_id, cif_version_id),
                )
                if cursor.fetchone() is not None:
                    raise ClientCifConflict(
                        "Confirmed CIF information requires a new review/version cycle."
                    )
                if cif_information_from_row(current) != expected:
                    raise ClientCifConflict("CIF changed; refresh the office review.")
                changed_fields = [
                    field
                    for field in (*_CIF_INFORMATION_FIELDS, "identity_information")
                    if expected.get(field) != corrected.get(field)
                ]
                if not changed_fields:
                    return _review_record_from_row(current)
                cursor.execute(
                    f"""
                    update lending.client_cif_versions
                    set full_name = %s,
                        phone_number = %s,
                        email = %s,
                        present_address = %s,
                        identity_information = %s,
                        updated_at = now()
                    where id = %s and client_id = %s
                      and is_current = true and status = 'draft'
                    returning {_CIF_RETURNING_COLUMNS}, identity_information
                    """,
                    (
                        corrected["full_name"],
                        corrected["phone_number"],
                        corrected["email"],
                        corrected["present_address"],
                        Jsonb(corrected["identity_information"])
                        if "identity_information" in corrected
                        else None,
                        cif_version_id,
                        client_id,
                    ),
                )
                updated = cursor.fetchone()
                if updated is None:
                    raise ClientCifConflict(
                        "The current CIF draft could not be corrected."
                    )
                cursor.execute(
                    """
                    insert into core.audit_logs (
                        actor_user_id, action, target_type, target_id, details
                    )
                    values (%s, 'client_cif.draft_information_corrected',
                            'client_cif_version', %s,
                            jsonb_build_object('client_id', %s::text,
                                               'changed_fields', to_jsonb(%s::text[]),
                                               'reason', %s::text))
                    """,
                    (
                        actor_user_id,
                        cif_version_id,
                        client_id,
                        changed_fields,
                        normalized_reason,
                    ),
                )
                return _review_record_from_row(updated)

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
        cif_version_id: UUID | None = None,
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
                      and (%s::uuid is null or id = %s)
                    returning {_CIF_RETURNING_COLUMNS}
                    """,
                    (
                        normalized_reference,
                        normalized_status,
                        client_id,
                        cif_version_id,
                        cif_version_id,
                    ),
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
        cif_version_id: UUID | None = None,
    ) -> ClientCifVersion:
        """Activate a ready current CIF and the existing Client exactly once."""

        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    select {_CIF_SELECT_COLUMNS}, cif.identity_information
                    from lending.client_cif_versions cif
                    join lending.client_onboarding_applicants applicant
                      on applicant.promoted_client_id = cif.client_id
                    join lending.clients client
                      on client.id = cif.client_id
                    where cif.client_id = %s
                      and cif.is_current = true
                      and (%s::uuid is null or cif.id = %s)
                      and cif.status in ('draft', 'active')
                      and applicant.status = 'eligible_for_cif'
                      and (
                            (cif.status = 'draft' and (client.status = 'inactive' or (
                                client.status = 'active' and exists (
                                    select 1 from lending.client_cif_review_cycles cycle where cycle.cif_version_id = cif.id
                                ))))
                            or (cif.status = 'active' and client.status = 'active')
                      )
                    limit 1
                    for update of cif, applicant, client
                    """,
                    (client_id, cif_version_id, cif_version_id),
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
                    "select review_snapshot, applicant_confirmation_evidence_reference, witnessed_by_user_id "
                    "from lending.client_cif_review_confirmations where client_id=%s and cif_version_id=%s",
                    (client_id, current["id"]),
                )
                confirmation = cursor.fetchone()
                if confirmation is None or confirmation[
                    "review_snapshot"
                ] != cif_information_from_row(current):
                    raise ClientCifConflict(
                        "CIF activation requires confirmation of the exact saved information."
                    )
                try:
                    require_evidence(
                        cursor,
                        evidence_reference=confirmation[
                            "applicant_confirmation_evidence_reference"
                        ],
                        actor_user_id=confirmation["witnessed_by_user_id"],
                        client_id=client_id,
                        purpose="cif_review",
                        subject_id=current["id"],
                        review_snapshot=cif_review_snapshot(
                            client_id=client_id,
                            cif_version_id=current["id"],
                            information=confirmation["review_snapshot"],
                        ),
                    )
                except OfficeReviewEvidenceConflict as error:
                    raise ClientCifConflict(str(error)) from error

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
