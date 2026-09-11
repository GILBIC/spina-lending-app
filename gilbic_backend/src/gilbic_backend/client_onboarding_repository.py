from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, cast
from uuid import UUID

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


class PostgresClientOnboardingRepository:
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
