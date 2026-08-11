from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .database import open_connection
from .eir_cash_allocation import EirCashSourceEvent
from .greenfield_regular_eir_rollforward import (
    GreenfieldRegularRenewalRollForward,
    build_greenfield_regular_renewal_rollforward,
)


MAX_SOURCE_EVENTS = 5000
READY_TARGET_STATUS = "greenfield_regular_renewal_rollforward_target_ready"


class GreenfieldRegularRenewalRollForwardError(RuntimeError):
    code = "greenfield_regular_renewal_rollforward_error"


@dataclass(frozen=True, slots=True)
class GreenfieldRegularRenewalRollForwardPreview:
    renewal_execution_event_id: UUID
    renewal_disbursement_event_id: UUID
    old_loan_id: UUID
    old_loan_number: str
    new_loan_id: UUID
    new_loan_number: str
    client_id: UUID
    client_code: str
    client_name: str
    target_date: date
    executed_at: datetime
    old_loan_settlement_amount: Decimal
    execution_external_reference: str
    renewal_source_readiness_status: str
    renewal_source_event_key: str
    anchor_posting_id: UUID | None
    anchor_disbursement_event_id: UUID | None
    anchor_journal_entry_id: UUID | None
    anchor_entry_number: str | None
    anchor_date: date | None
    initial_gross_carrying_amount: Decimal | None
    initial_loan_component: Decimal | None
    initial_accrued_interest_component: Decimal | None
    daily_eir: Decimal | None
    daily_eir_percent: Decimal | None
    contractual_due_date: date | None
    schedule_id: UUID | None
    contract_reference: str | None
    contract_evidence_reference: str | None
    anchor_readiness_status: str | None
    anchor_source_key: str | None
    source_event_count_before_target: int
    same_day_target_collection_count: int
    readiness_status: str
    target_source_key: str
    rollforward_policy_version: str
    measurement_preview_enabled: bool
    accounting_carrying_amount_ready: bool
    journal_lines_enabled: bool
    automatic_source_posting: bool
    rollforward: GreenfieldRegularRenewalRollForward | None


class PostgresGreenfieldRegularRenewalRollForwardRepository:
    def list_previews(
        self,
        *,
        readiness_status: str | None = None,
        renewal_execution_event_id: UUID | None = None,
        old_loan_id: UUID | None = None,
        limit: int = 100,
    ) -> tuple[GreenfieldRegularRenewalRollForwardPreview, ...]:
        safe_limit = max(1, min(int(limit), 250))
        normalized_status = (
            readiness_status.strip()
            if readiness_status and readiness_status.strip()
            else None
        )
        try:
            with open_connection() as connection:
                connection.execute(
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
                )
                with connection.cursor(row_factory=dict_row) as cursor:
                    rows = cursor.execute(
                        """
                        select *
                        from accounting.greenfield_regular_renewal_rollforward_targets
                        where (%s::text is null or readiness_status = %s::text)
                          and (%s::uuid is null or renewal_execution_event_id = %s::uuid)
                          and (%s::uuid is null or old_loan_id = %s::uuid)
                        order by target_date desc, old_loan_number, renewal_execution_event_id
                        limit %s
                        """,
                        (
                            normalized_status,
                            normalized_status,
                            renewal_execution_event_id,
                            renewal_execution_event_id,
                            old_loan_id,
                            old_loan_id,
                            safe_limit,
                        ),
                    ).fetchall()

                    previews: list[GreenfieldRegularRenewalRollForwardPreview] = []
                    for row in rows:
                        rollforward = None
                        if (
                            str(row["readiness_status"]) == READY_TARGET_STATUS
                            and bool(row["measurement_preview_enabled"])
                        ):
                            events = self._load_source_events(
                                cursor,
                                loan_id=row["old_loan_id"],
                                anchor_date=row["anchor_date"],
                                target_date=row["target_date"],
                            )
                            if len(events) > MAX_SOURCE_EVENTS:
                                raise GreenfieldRegularRenewalRollForwardError(
                                    "Greenfield Regular renewal source history exceeded the protected 5,000-event preview limit."
                                )
                            rollforward = build_greenfield_regular_renewal_rollforward(
                                loan_id=row["old_loan_id"],
                                anchor_date=row["anchor_date"],
                                target_date=row["target_date"],
                                contractual_due_date=row["contractual_due_date"],
                                daily_eir=Decimal(row["daily_eir"]),
                                initial_gross_carrying_amount=Decimal(
                                    row["initial_gross_carrying_amount"]
                                ),
                                initial_accrued_interest_component=Decimal(
                                    row["initial_accrued_interest_component"]
                                ),
                                initial_loan_component=Decimal(
                                    row["initial_loan_component"]
                                ),
                                source_events=events,
                            )
                        previews.append(self._from_row(row, rollforward=rollforward))
            return tuple(previews)
        except GreenfieldRegularRenewalRollForwardError:
            raise
        except psycopg.Error as error:
            message = str(error).split("CONTEXT:", 1)[0].strip()
            raise GreenfieldRegularRenewalRollForwardError(
                message
                or "Greenfield Regular renewal roll-forward preview could not be loaded."
            ) from error

    @staticmethod
    def _load_source_events(
        cursor,
        *,
        loan_id: UUID,
        anchor_date: date,
        target_date: date,
    ) -> tuple[EirCashSourceEvent, ...]:
        rows = cursor.execute(
            """
            select
                transaction.id as transaction_id,
                transaction.collection_date,
                transaction.accepted_at,
                transaction.entry_type,
                transaction.amount,
                transaction.is_voided
            from lending.collection_transactions transaction
            where transaction.loan_id = %s
              and transaction.collection_date > %s
              and transaction.collection_date < %s
              and transaction.is_voided = false
              and transaction.entry_type in ('payment', 'advance')
              and transaction.amount > 0
            order by transaction.collection_date, transaction.accepted_at, transaction.id
            limit %s
            """,
            (loan_id, anchor_date, target_date, MAX_SOURCE_EVENTS + 1),
        ).fetchall()
        return tuple(
            EirCashSourceEvent(
                transaction_id=UUID(str(row["transaction_id"])),
                collection_date=row["collection_date"],
                accepted_at=row["accepted_at"],
                entry_type=str(row["entry_type"]),
                amount=Decimal(row["amount"]),
                is_voided=bool(row["is_voided"]),
            )
            for row in rows
        )

    @staticmethod
    def _from_row(
        row,
        *,
        rollforward: GreenfieldRegularRenewalRollForward | None,
    ) -> GreenfieldRegularRenewalRollForwardPreview:
        return GreenfieldRegularRenewalRollForwardPreview(
            renewal_execution_event_id=row["renewal_execution_event_id"],
            renewal_disbursement_event_id=row["renewal_disbursement_event_id"],
            old_loan_id=row["old_loan_id"],
            old_loan_number=str(row["old_loan_number"]),
            new_loan_id=row["new_loan_id"],
            new_loan_number=str(row["new_loan_number"]),
            client_id=row["client_id"],
            client_code=str(row["client_code"]),
            client_name=str(row["client_name"]),
            target_date=row["target_date"],
            executed_at=row["executed_at"],
            old_loan_settlement_amount=Decimal(row["old_loan_settlement_amount"]),
            execution_external_reference=str(row["execution_external_reference"]),
            renewal_source_readiness_status=str(
                row["renewal_source_readiness_status"]
            ),
            renewal_source_event_key=str(row["renewal_source_event_key"]),
            anchor_posting_id=row["anchor_posting_id"],
            anchor_disbursement_event_id=row["anchor_disbursement_event_id"],
            anchor_journal_entry_id=row["anchor_journal_entry_id"],
            anchor_entry_number=(
                str(row["anchor_entry_number"])
                if row["anchor_entry_number"]
                else None
            ),
            anchor_date=row["anchor_date"],
            initial_gross_carrying_amount=(
                Decimal(row["initial_gross_carrying_amount"])
                if row["initial_gross_carrying_amount"] is not None
                else None
            ),
            initial_loan_component=(
                Decimal(row["initial_loan_component"])
                if row["initial_loan_component"] is not None
                else None
            ),
            initial_accrued_interest_component=(
                Decimal(row["initial_accrued_interest_component"])
                if row["initial_accrued_interest_component"] is not None
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
            contractual_due_date=row["contractual_due_date"],
            schedule_id=row["schedule_id"],
            contract_reference=(
                str(row["contract_reference"])
                if row["contract_reference"]
                else None
            ),
            contract_evidence_reference=(
                str(row["contract_evidence_reference"])
                if row["contract_evidence_reference"]
                else None
            ),
            anchor_readiness_status=(
                str(row["anchor_readiness_status"])
                if row["anchor_readiness_status"]
                else None
            ),
            anchor_source_key=(
                str(row["anchor_source_key"]) if row["anchor_source_key"] else None
            ),
            source_event_count_before_target=int(
                row["source_event_count_before_target"] or 0
            ),
            same_day_target_collection_count=int(
                row["same_day_target_collection_count"] or 0
            ),
            readiness_status=str(row["readiness_status"]),
            target_source_key=str(row["target_source_key"]),
            rollforward_policy_version=str(row["rollforward_policy_version"]),
            measurement_preview_enabled=bool(row["measurement_preview_enabled"]),
            accounting_carrying_amount_ready=bool(
                row["accounting_carrying_amount_ready"]
            ),
            journal_lines_enabled=bool(row["journal_lines_enabled"]),
            automatic_source_posting=bool(row["automatic_source_posting"]),
            rollforward=rollforward,
        )
