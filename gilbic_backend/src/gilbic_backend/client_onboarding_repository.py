from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

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
