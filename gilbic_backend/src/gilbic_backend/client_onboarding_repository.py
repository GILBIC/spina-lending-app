from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, cast
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
