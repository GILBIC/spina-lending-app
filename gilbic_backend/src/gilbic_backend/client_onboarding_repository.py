from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, cast
from uuid import UUID

from psycopg.rows import dict_row

from .database import open_connection

ClientOnboardingStatus = Literal[
    "requirements_incomplete",
    "under_verification",
    "eligible_for_cif",
    "requirements_rejected",
]


@dataclass(frozen=True, slots=True)
class ClientOnboardingRecord:
    application_reference: str
    status: ClientOnboardingStatus
    promoted_client_id: UUID | None = None


class ClientOnboardingAccessDenied(PermissionError):
    pass


_OFFICE_AUTH_SQL = """
    select 1 from core.users actor
    where actor.id = %s and actor.status = 'active'
      and exists (
        select 1 from core.user_roles user_role
        join core.roles role on role.id = user_role.role_id
        join core.role_permissions permission on permission.role_id = role.id
        where user_role.user_id = actor.id and role.code = any(%s)
          and permission.permission_code = %s
      )
"""

_SEARCH_OFFICE_CASES_SQL = """
    select a.id as applicant_id, a.application_reference as intake_reference,
           a.promoted_client_id as client_id, a.full_name, a.phone_number,
           a.status as intake_status, a.created_at, a.updated_at
    from lending.client_onboarding_applicants a
    where (%(status)s::text is null or a.status = %(status)s)
      and (%(q)s = '' or a.full_name ilike %(pattern)s
           or a.application_reference ilike %(pattern)s
           or (%(phone)s::text is not null and
               regexp_replace(a.phone_number, '[^0-9]', '', 'g') like %(phone)s)
           or exists (select 1 from lending.loan_applications app
                      where app.client_id = a.promoted_client_id
                        and app.application_reference ilike %(pattern)s))
      and (%(created_at)s::timestamptz is null or
           (a.created_at, a.id) < (%(created_at)s::timestamptz, %(id)s::uuid))
    order by a.created_at desc, a.id desc
    limit %(take)s
"""

_LIST_OFFICE_APPLICATIONS_SQL = """
    with page as materialized (
        select id, application_reference, client_id, created_at
        from lending.loan_applications
        where client_id = %(client_id)s
          and (%(created_at)s::timestamptz is null or
               (created_at, id) < (%(created_at)s::timestamptz, %(id)s::uuid))
        order by created_at desc, id desc limit %(take)s
    )
    select page.id as application_id, page.application_reference,
           page.client_id, page.created_at,
           latest.id as application_version_id, latest.version_number, latest.recorded_at
    from page
    left join lateral (
        select v.id, v.version_number, v.recorded_at
        from lending.loan_application_versions v
        where v.application_id = page.id and v.client_id = page.client_id
        order by v.version_number desc limit 1
    ) latest on true
    order by page.created_at desc, page.id desc
"""


def _finder_inputs(q: str, status: str | None, limit: int, cursor: str | None) -> str:
    if not isinstance(q, str):
        raise ValueError("Finder query is invalid.")  # noqa: TRY004 -- uniform finder validation boundary
    query = q.strip().lower()
    if query and not 3 <= len(query) <= 200:
        raise ValueError("Finder query is invalid.")
    if status is not None and status not in (
        "requirements_incomplete",
        "under_verification",
        "eligible_for_cif",
        "requirements_rejected",
    ):
        raise ValueError("Finder status is invalid.")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Finder limit is invalid.")
    if cursor is not None and (
        not isinstance(cursor, str) or not 1 <= len(cursor) <= 2048
    ):
        raise ValueError("Finder cursor is invalid.")
    return query


def _finder_scope(parts: list[str | None]) -> str:
    # Scope fingerprints keep names, phones and exact references out of tokens.
    return hashlib.sha256(json.dumps(parts, separators=(",", ":")).encode()).hexdigest()


def _decode_finder_cursor(
    token: str | None, scope: str
) -> tuple[datetime | None, UUID | None]:
    if token is None:
        return None, None
    try:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", token):
            raise ValueError
        raw = base64.b64decode(
            token + "=" * (-len(token) % 4), altchars=b"-_", validate=True
        )
        payload = json.loads(raw)
        if (
            not isinstance(payload, dict)
            or set(payload) != {"v", "scope", "created_at", "id"}
            or type(payload["v"]) is not int
            or payload["v"] != 1
            or payload["scope"] != scope
        ):
            raise ValueError
        created_at = datetime.fromisoformat(payload["created_at"])
        identity = UUID(payload["id"])
        if created_at.tzinfo is None or str(identity) != payload["id"]:
            raise ValueError
        canonical = (
            base64.urlsafe_b64encode(
                json.dumps(payload, separators=(",", ":")).encode()
            )
            .decode()
            .rstrip("=")
        )
        if canonical != token:
            raise ValueError
        return created_at, identity
    except (ValueError, TypeError, KeyError, OverflowError) as error:
        raise ValueError("Finder cursor is invalid for this selection.") from error


def _finder_page(
    rows: list[dict[str, Any]], *, limit: int, scope: str, identity: str
) -> dict[str, Any]:
    has_more = len(rows) > limit
    items = rows[:limit]
    token = None
    if has_more:
        last = items[-1]
        payload = {
            "v": 1,
            "scope": scope,
            "created_at": last["created_at"].isoformat(),
            "id": str(last[identity]),
        }
        token = (
            base64.urlsafe_b64encode(
                json.dumps(payload, separators=(",", ":")).encode()
            )
            .decode()
            .rstrip("=")
        )
    return {
        "items": items,
        "next_cursor": token,
        "has_more": has_more,
        "as_of": datetime.now(UTC),
    }


def _require_office_reader(cursor, actor_user_id: UUID) -> None:
    if (
        cursor.execute(
            _OFFICE_AUTH_SQL,
            (
                actor_user_id,
                ["employee", "management"],
                "client_onboarding.requirement.review",
            ),
        ).fetchone()
        is None
    ):
        raise ClientOnboardingAccessDenied(
            "An active authorized onboarding account is required."
        )


class PostgresClientOnboardingRepository:
    def search_office_cases(
        self,
        *,
        actor_user_id: UUID,
        q: str = "",
        status: ClientOnboardingStatus | None = None,
        limit: int = 25,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        query = _finder_inputs(q, status, limit, cursor)
        scope = _finder_scope(["intakes", query, status])
        created_at, identity = _decode_finder_cursor(cursor, scope)
        pattern = (
            "%"
            + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            + "%"
        )
        digits = "".join(c for c in query if c in "0123456789")
        phone = (
            "%" + digits + "%"
            if digits and re.fullmatch(r"[0-9+().\s-]+", query)
            else None
        )
        with (
            open_connection() as connection,
            connection.cursor(row_factory=dict_row) as reader,
        ):
            _require_office_reader(reader, actor_user_id)
            rows = reader.execute(
                _SEARCH_OFFICE_CASES_SQL,
                {
                    "q": query,
                    "pattern": pattern,
                    "phone": phone,
                    "status": status,
                    "created_at": created_at,
                    "id": identity,
                    "take": limit + 1,
                },
            ).fetchall()
        return _finder_page(rows, limit=limit, scope=scope, identity="applicant_id")

    def list_office_applications(
        self,
        *,
        actor_user_id: UUID,
        application_reference: str,
        limit: int = 25,
        cursor: str | None = None,
    ) -> dict[str, Any] | None:
        _finder_inputs("", None, limit, cursor)
        if (
            not isinstance(application_reference, str)
            or not application_reference.strip()
        ):
            raise ValueError("Office intake reference must be a nonblank string.")
        reference = application_reference.strip()
        # Check syntax before database acquisition; relationship-bound scope is
        # verified after resolving the currently authorized exact intake.
        if cursor is not None:
            try:
                raw = base64.b64decode(
                    cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True
                )
                candidate_scope = json.loads(raw)["scope"]
                if not isinstance(candidate_scope, str):
                    raise TypeError
                _decode_finder_cursor(cursor, candidate_scope)
            except (ValueError, TypeError, KeyError) as error:
                raise ValueError("Finder cursor is invalid.") from error
        with (
            open_connection() as connection,
            connection.cursor(row_factory=dict_row) as reader,
        ):
            _require_office_reader(reader, actor_user_id)
            intake = reader.execute(
                """
                    select id as applicant_id, application_reference as intake_reference,
                           promoted_client_id as client_id, status as intake_status
                    from lending.client_onboarding_applicants
                    where lower(application_reference) = lower(%s)
                """,
                (reference,),
            ).fetchone()
            if intake is None:
                return None
            scope = _finder_scope(
                ["applications", str(intake["applicant_id"]), str(intake["client_id"])]
            )
            created_at, identity = _decode_finder_cursor(cursor, scope)
            rows = (
                reader.execute(
                    _LIST_OFFICE_APPLICATIONS_SQL,
                    {
                        "client_id": intake["client_id"],
                        "created_at": created_at,
                        "id": identity,
                        "take": limit + 1,
                    },
                ).fetchall()
                if intake["client_id"] is not None
                else []
            )
        return {
            **_finder_page(rows, limit=limit, scope=scope, identity="application_id"),
            "intake": intake,
        }

    def get_case_by_reference(
        self,
        *,
        actor_user_id: UUID,
        application_reference: str,
        scope: Literal["office", "collector"],
    ) -> dict[str, Any] | None:
        """Read one exact intake case with the minimum role-specific projection."""
        if not isinstance(application_reference, str) or not application_reference.strip():
            raise ValueError("Office intake reference must be a nonblank string.")
        if scope not in ("office", "collector"):
            raise ValueError("Onboarding case scope is invalid.")
        reference = application_reference.strip()
        roles = ["employee", "management"] if scope == "office" else ["collector"]
        permission = (
            "client_onboarding.requirement.review" if scope == "office"
            else "client_onboarding.visit.record"
        )
        common = """
            id as applicant_id, application_reference, status, full_name,
            phone_number, present_address, collector_visit_status,
            collector_visit_note, collector_visit_evidence_reference
        """
        office = """,
            email, promoted_client_id as client_id, national_id_status,
            national_id_egov_evidence_reference, tin_id_status,
            tin_id_egov_evidence_reference, meralco_bill_status,
            meralco_bill_evidence_reference, privacy_consent,
            accuracy_declaration, bypassed_requirements, bypass_reason
        """ if scope == "office" else ""
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                allowed = cursor.execute(
                    """
                    select 1 from core.users actor
                    where actor.id = %s and actor.status = 'active'
                      and exists (
                        select 1 from core.user_roles user_role
                        join core.roles role on role.id = user_role.role_id
                        join core.role_permissions permission on permission.role_id = role.id
                        where user_role.user_id = actor.id and role.code = any(%s)
                          and permission.permission_code = %s
                      )
                    """,
                    (actor_user_id, roles, permission),
                ).fetchone()
                if allowed is None:
                    raise ClientOnboardingAccessDenied(
                        "An active authorized onboarding account is required."
                    )
                row = cursor.execute(
                    f"""
                    select {common}{office}
                    from lending.client_onboarding_applicants
                    where lower(application_reference) = lower(%s)
                    """,
                    (reference,),
                ).fetchone()
        if row is None:
            return None
        visit = {
            "status": row.pop("collector_visit_status"),
            "note": row.pop("collector_visit_note"),
            "evidence_reference": row.pop("collector_visit_evidence_reference"),
        }
        if scope == "collector":
            row["collector_visit"] = visit
        else:
            row["requirements"] = {
                name: {
                    "status": row.pop(f"{name}_status"),
                    "evidence_reference": row.pop(evidence),
                }
                for name, evidence in (
                    ("national_id", "national_id_egov_evidence_reference"),
                    ("tin_id", "tin_id_egov_evidence_reference"),
                    ("meralco_bill", "meralco_bill_evidence_reference"),
                )
            }
            row["requirements"]["collector_visit"] = visit
        return row

    def find_cif_client_by_reference(
        self, *, application_reference: str
    ) -> ClientOnboardingRecord | None:
        """Find an eligible Client by the exact office intake reference."""
        if not isinstance(application_reference, str):
            raise ValueError("Office intake reference must be a nonblank string.")
        reference = application_reference.strip()
        if not reference:
            raise ValueError("Office intake reference must be a nonblank string.")

        with open_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select
                        applicant.application_reference,
                        applicant.status,
                        applicant.promoted_client_id
                    from lending.client_onboarding_applicants as applicant
                    join lending.clients as client
                        on client.id = applicant.promoted_client_id
                    where lower(applicant.application_reference) = lower(%s)
                      and applicant.status = 'eligible_for_cif'
                      and client.status in ('inactive', 'active')
                    """,
                    (reference,),
                )
                row = cursor.fetchone()

        if row is None:
            return None
        return ClientOnboardingRecord(
            application_reference=str(row[0]),
            status=cast(ClientOnboardingStatus, str(row[1])),
            promoted_client_id=row[2],
        )

    def submit_applicant(
        self,
        *,
        full_name: str,
        phone_number: str,
        email: str | None,
        present_address: str,
        national_id_egov_evidence_reference: str,
        tin_id_egov_evidence_reference: str,
        meralco_bill_evidence_reference: str,
        privacy_consent: bool,
        accuracy_declaration: bool,
    ) -> ClientOnboardingRecord:
        with open_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "select nextval('lending.client_onboarding_reference_seq')"
                )
                sequence_row = cursor.fetchone()
                if sequence_row is None:
                    raise RuntimeError("Unable to allocate onboarding reference.")

                sequence_value = int(sequence_row[0])
                application_reference = (
                    f"APP-{datetime.now(UTC).year}-{sequence_value:06d}"
                )
                cursor.execute(
                    """
                    insert into lending.client_onboarding_applicants (
                        application_reference,
                        full_name,
                        phone_number,
                        email,
                        present_address,
                        national_id_egov_evidence_reference,
                        tin_id_egov_evidence_reference,
                        meralco_bill_evidence_reference,
                        privacy_consent,
                        accuracy_declaration
                    )
                    values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        application_reference,
                        full_name,
                        phone_number,
                        email,
                        present_address,
                        national_id_egov_evidence_reference,
                        tin_id_egov_evidence_reference,
                        meralco_bill_evidence_reference,
                        privacy_consent,
                        accuracy_declaration,
                    ),
                )

        return ClientOnboardingRecord(
            application_reference=application_reference,
            status="requirements_incomplete",
        )

    def review_document_requirements(
        self,
        *,
        actor_user_id: UUID,
        applicant_id: UUID,
        national_id_status: Literal["passed", "failed"],
        tin_id_status: Literal["passed", "failed"],
        meralco_bill_status: Literal["passed", "failed"],
    ) -> ClientOnboardingRecord:
        next_status: ClientOnboardingStatus = (
            "requirements_rejected"
            if "failed"
            in (national_id_status, tin_id_status, meralco_bill_status)
            else "under_verification"
        )
        with open_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    update lending.client_onboarding_applicants
                    set
                        national_id_status = %s,
                        tin_id_status = %s,
                        meralco_bill_status = %s,
                        status = %s,
                        eligibility_reviewed_by_user_id = %s,
                        eligibility_reviewed_at = now(),
                        updated_at = now()
                    where id = %s
                    returning application_reference, status
                    """,
                    (
                        national_id_status,
                        tin_id_status,
                        meralco_bill_status,
                        next_status,
                        actor_user_id,
                        applicant_id,
                    ),
                )
                row = cursor.fetchone()
                if row is None:
                    raise RuntimeError("Onboarding applicant was not found.")

                cursor.execute(
                    """
                    insert into core.audit_logs (
                        actor_user_id,
                        action,
                        target_type,
                        target_id,
                        details
                    )
                    values (
                        %s,
                        'client_onboarding.documents_reviewed',
                        'client_onboarding_applicant',
                        %s,
                        jsonb_build_object(
                            'national_id_status', %s::text,
                            'tin_id_status', %s::text,
                            'meralco_bill_status', %s::text
                        )
                    )
                    """,
                    (
                        actor_user_id,
                        applicant_id,
                        national_id_status,
                        tin_id_status,
                        meralco_bill_status,
                    ),
                )

        return ClientOnboardingRecord(
            application_reference=str(row[0]),
            status=cast(ClientOnboardingStatus, str(row[1])),
        )

    def record_collector_visit(
        self,
        *,
        actor_user_id: UUID,
        applicant_id: UUID,
        result: Literal["passed", "failed"],
        note: str,
        evidence_reference: str | None,
    ) -> ClientOnboardingRecord:
        with open_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    update lending.client_onboarding_applicants
                    set
                        collector_visit_status = %s,
                        collector_visit_evidence_reference = %s,
                        collector_visit_note = %s,
                        collector_visit_by_user_id = %s,
                        collector_visit_completed_at = now(),
                        status = case
                            when status = 'eligible_for_cif' then status
                            when %s = 'failed' then 'requirements_rejected'
                            else 'under_verification'
                        end,
                        updated_at = now()
                    where id = %s
                    returning application_reference, status
                    """,
                    (
                        result,
                        evidence_reference,
                        note,
                        actor_user_id,
                        result,
                        applicant_id,
                    ),
                )
                row = cursor.fetchone()
                if row is None:
                    raise RuntimeError("Onboarding applicant was not found.")

                cursor.execute(
                    """
                    insert into core.audit_logs (
                        actor_user_id,
                        action,
                        target_type,
                        target_id,
                        details
                    )
                    values (
                        %s,
                        'client_onboarding.collector_visit_recorded',
                        'client_onboarding_applicant',
                        %s,
                        jsonb_build_object('result', %s::text)
                    )
                    """,
                    (actor_user_id, applicant_id, result),
                )

        return ClientOnboardingRecord(
            application_reference=str(row[0]),
            status=cast(ClientOnboardingStatus, str(row[1])),
        )

    def _promote_locked(
        self,
        *,
        cursor: Any,
        actor_user_id: UUID,
        applicant_id: UUID,
        application_reference: str,
        full_name: str,
        phone_number: str,
    ) -> ClientOnboardingRecord:
        client_code = application_reference.replace("APP-", "CLIENT-", 1)
        cursor.execute(
            """
            insert into lending.clients (
                client_code,
                full_name,
                phone_number,
                area,
                status,
                user_id
            )
            values (%s, %s, %s, null, 'inactive', null)
            returning id
            """,
            (client_code, full_name, phone_number),
        )
        client_row = cursor.fetchone()
        if client_row is None:
            raise RuntimeError("Unable to create Client identity.")
        client_id = client_row[0]

        cursor.execute(
            """
            update lending.client_onboarding_applicants
            set
                status = 'eligible_for_cif',
                promoted_client_id = %s,
                eligibility_reviewed_by_user_id = %s,
                eligibility_reviewed_at = now(),
                updated_at = now()
            where id = %s
            """,
            (client_id, actor_user_id, applicant_id),
        )

        cursor.execute(
            """
            insert into core.audit_logs (
                actor_user_id,
                action,
                target_type,
                target_id,
                details
            )
            values (
                %s,
                'client_onboarding.eligibility_approved',
                'client_onboarding_applicant',
                %s,
                jsonb_build_object('client_id', %s::text)
            )
            """,
            (actor_user_id, applicant_id, client_id),
        )
        cursor.execute(
            """
            insert into core.audit_logs (
                actor_user_id,
                action,
                target_type,
                target_id,
                details
            )
            values (
                %s,
                'client_onboarding.client_created',
                'client',
                %s,
                jsonb_build_object('application_reference', %s::text)
            )
            """,
            (actor_user_id, client_id, application_reference),
        )

        return ClientOnboardingRecord(
            application_reference=application_reference,
            status="eligible_for_cif",
            promoted_client_id=client_id,
        )

    def approve_normal_eligibility(
        self,
        *,
        actor_user_id: UUID,
        applicant_id: UUID,
    ) -> ClientOnboardingRecord:
        with open_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select
                        application_reference,
                        status,
                        full_name,
                        phone_number,
                        national_id_status,
                        tin_id_status,
                        meralco_bill_status,
                        collector_visit_status,
                        promoted_client_id
                    from lending.client_onboarding_applicants
                    where id = %s
                    for update
                    """,
                    (applicant_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise RuntimeError("Onboarding applicant was not found.")

                application_reference = str(row[0])
                current_status = cast(ClientOnboardingStatus, str(row[1]))
                promoted_client_id = row[8]
                if current_status == "eligible_for_cif" and promoted_client_id is not None:
                    return ClientOnboardingRecord(
                        application_reference=application_reference,
                        status=current_status,
                        promoted_client_id=promoted_client_id,
                    )

                requirements = (row[4], row[5], row[6], row[7])
                if any(str(requirement) != "passed" for requirement in requirements):
                    return ClientOnboardingRecord(
                        application_reference=application_reference,
                        status=current_status,
                    )

                return self._promote_locked(
                    cursor=cursor,
                    actor_user_id=actor_user_id,
                    applicant_id=applicant_id,
                    application_reference=application_reference,
                    full_name=str(row[2]),
                    phone_number=str(row[3]),
                )

    def bypass_and_approve_eligibility(
        self,
        *,
        actor_user_id: UUID,
        applicant_id: UUID,
        bypassed_requirements: list[str] | tuple[str, ...],
        reason: str,
    ) -> ClientOnboardingRecord:
        with open_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select
                        application_reference,
                        status,
                        full_name,
                        phone_number,
                        national_id_status,
                        tin_id_status,
                        meralco_bill_status,
                        collector_visit_status,
                        promoted_client_id
                    from lending.client_onboarding_applicants
                    where id = %s
                    for update
                    """,
                    (applicant_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise RuntimeError("Onboarding applicant was not found.")

                application_reference = str(row[0])
                current_status = cast(ClientOnboardingStatus, str(row[1]))
                promoted_client_id = row[8]
                if current_status == "eligible_for_cif" and promoted_client_id is not None:
                    return ClientOnboardingRecord(
                        application_reference=application_reference,
                        status=current_status,
                        promoted_client_id=promoted_client_id,
                    )

                requirements_by_name = {
                    "national_id": str(row[4]),
                    "tin_id": str(row[5]),
                    "meralco_bill": str(row[6]),
                    "collector_visit": str(row[7]),
                }
                non_passed = {
                    name
                    for name, requirement_status in requirements_by_name.items()
                    if requirement_status != "passed"
                }
                normalized_requirements = sorted(set(bypassed_requirements))
                normalized_reason = " ".join(reason.split())

                if (
                    not non_passed
                    or set(normalized_requirements) != non_passed
                    or len(normalized_reason) < 3
                ):
                    return ClientOnboardingRecord(
                        application_reference=application_reference,
                        status=current_status,
                    )

                cursor.execute(
                    """
                    update lending.client_onboarding_applicants
                    set
                        bypassed_requirements = %s::text[],
                        bypass_reason = %s,
                        bypassed_by_user_id = %s,
                        bypassed_at = now(),
                        updated_at = now()
                    where id = %s
                    """,
                    (
                        normalized_requirements,
                        normalized_reason,
                        actor_user_id,
                        applicant_id,
                    ),
                )
                cursor.execute(
                    """
                    insert into core.audit_logs (
                        actor_user_id,
                        action,
                        target_type,
                        target_id,
                        details
                    )
                    values (
                        %s,
                        'client_onboarding.requirements_bypassed',
                        'client_onboarding_applicant',
                        %s,
                        jsonb_build_object(
                            'bypassed_requirements', to_jsonb(%s::text[]),
                            'reason', %s::text
                        )
                    )
                    """,
                    (
                        actor_user_id,
                        applicant_id,
                        normalized_requirements,
                        normalized_reason,
                    ),
                )

                return self._promote_locked(
                    cursor=cursor,
                    actor_user_id=actor_user_id,
                    applicant_id=applicant_id,
                    application_reference=application_reference,
                    full_name=str(row[2]),
                    phone_number=str(row[3]),
                )
