from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .database import open_connection


class GreenfieldRegularEirAnchorError(RuntimeError):
    code = "greenfield_regular_eir_anchor_error"


@dataclass(frozen=True, slots=True)
class GreenfieldRegularEirAnchorRecord:
    posting_id: UUID
    disbursement_event_id: UUID
    loan_id: UUID
    loan_number: str
    client_id: UUID
    client_code: str
    client_name: str
    journal_entry_id: UUID
    entry_number: str
    release_source_event_key: str
    anchor_date: date
    disbursed_at: datetime
    initial_gross_carrying_amount: Decimal
    initial_loan_component: Decimal
    initial_accrued_interest_component: Decimal
    schedule_id: UUID | None
    schedule_version: int | None
    schedule_status: str | None
    payment_frequency: str | None
    contract_reference: str | None
    contract_signed_date: date | None
    schedule_effective_from: date | None
    registration_id: int | None
    evidence_basis: str | None
    evidence_reference: str | None
    installment_count: int | None
    first_due_date: date | None
    contractual_due_date: date | None
    contractual_cash_total: Decimal | None
    daily_eir: Decimal | None
    daily_eir_percent: Decimal | None
    pre_anchor_collection_count: int
    same_day_collection_count: int
    readiness_status: str
    anchor_source_key: str
    anchor_policy_version: str
    collection_journal_integration_enabled: bool
    journal_lines_enabled: bool
    automatic_source_posting: bool


class PostgresGreenfieldRegularEirAnchorRepository:
    def list_readiness(
        self,
        *,
        readiness_status: str | None = None,
        loan_id: UUID | None = None,
        limit: int = 100,
    ) -> tuple[GreenfieldRegularEirAnchorRecord, ...]:
        safe_limit = max(1, min(int(limit), 250))
        normalized_status = (
            readiness_status.strip() if readiness_status and readiness_status.strip() else None
        )
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    rows = cursor.execute(
                        """
                        select *
                        from accounting.greenfield_regular_eir_anchor_readiness
                        where (%s::text is null or readiness_status = %s::text)
                          and (%s::uuid is null or loan_id = %s::uuid)
                        order by anchor_date desc, loan_number, posting_id
                        limit %s
                        """,
                        (
                            normalized_status,
                            normalized_status,
                            loan_id,
                            loan_id,
                            safe_limit,
                        ),
                    ).fetchall()
            return tuple(self._from_row(row) for row in rows)
        except psycopg.Error as error:
            message = str(error).split("CONTEXT:", 1)[0].strip()
            raise GreenfieldRegularEirAnchorError(
                message or "Greenfield Regular EIR anchor readiness failed."
            ) from error

    @staticmethod
    def _from_row(row) -> GreenfieldRegularEirAnchorRecord:
        return GreenfieldRegularEirAnchorRecord(
            posting_id=row["posting_id"],
            disbursement_event_id=row["disbursement_event_id"],
            loan_id=row["loan_id"],
            loan_number=str(row["loan_number"]),
            client_id=row["client_id"],
            client_code=str(row["client_code"]),
            client_name=str(row["client_name"]),
            journal_entry_id=row["journal_entry_id"],
            entry_number=str(row["entry_number"]),
            release_source_event_key=str(row["release_source_event_key"]),
            anchor_date=row["anchor_date"],
            disbursed_at=row["disbursed_at"],
            initial_gross_carrying_amount=Decimal(row["initial_gross_carrying_amount"]),
            initial_loan_component=Decimal(row["initial_loan_component"]),
            initial_accrued_interest_component=Decimal(
                row["initial_accrued_interest_component"]
            ),
            schedule_id=row["schedule_id"],
            schedule_version=(
                int(row["schedule_version"])
                if row["schedule_version"] is not None
                else None
            ),
            schedule_status=(
                str(row["schedule_status"]) if row["schedule_status"] else None
            ),
            payment_frequency=(
                str(row["payment_frequency"]) if row["payment_frequency"] else None
            ),
            contract_reference=(
                str(row["contract_reference"]) if row["contract_reference"] else None
            ),
            contract_signed_date=row["contract_signed_date"],
            schedule_effective_from=row["schedule_effective_from"],
            registration_id=(
                int(row["registration_id"])
                if row["registration_id"] is not None
                else None
            ),
            evidence_basis=(
                str(row["evidence_basis"]) if row["evidence_basis"] else None
            ),
            evidence_reference=(
                str(row["evidence_reference"]) if row["evidence_reference"] else None
            ),
            installment_count=(
                int(row["installment_count"])
                if row["installment_count"] is not None
                else None
            ),
            first_due_date=row["first_due_date"],
            contractual_due_date=row["contractual_due_date"],
            contractual_cash_total=(
                Decimal(row["contractual_cash_total"])
                if row["contractual_cash_total"] is not None
                else None
            ),
            daily_eir=(
                Decimal(row["daily_eir"]) if row["daily_eir"] is not None else None
            ),
            daily_eir_percent=(
                Decimal(row["daily_eir_percent"])
                if row["daily_eir_percent"] is not None
                else None
            ),
            pre_anchor_collection_count=int(row["pre_anchor_collection_count"] or 0),
            same_day_collection_count=int(row["same_day_collection_count"] or 0),
            readiness_status=str(row["readiness_status"]),
            anchor_source_key=str(row["anchor_source_key"]),
            anchor_policy_version=str(row["anchor_policy_version"]),
            collection_journal_integration_enabled=bool(
                row["collection_journal_integration_enabled"]
            ),
            journal_lines_enabled=bool(row["journal_lines_enabled"]),
            automatic_source_posting=bool(row["automatic_source_posting"]),
        )
