from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from .db import Database


class EclA5AccountingBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class EclA5Action:
    loan_id: UUID
    loan_number: str
    loan_status: str
    calculation_mode: str
    credit_risk_review_id: int | None
    stage_label: str | None
    default_label: bool | None
    write_off_label: str | None
    recovery_label: str | None
    measurement_id: UUID | None
    measurement_version: int | None
    measurement_date: date | None
    calculation_digest: str | None
    measurement_status: str | None
    authoritative_ecl_amount: Decimal | None
    current_allowance_balance: Decimal
    loan_receivable_account_id: UUID | None
    loan_receivable_system_key: str | None
    accrued_interest_account_id: UUID | None
    loan_component: Decimal | None
    accrued_interest_component: Decimal | None
    gross_carrying_amount: Decimal | None
    writeoff_id: UUID | None
    recovery_transaction_id: UUID | None
    recovery_amount: Decimal | None
    a5_status: str
    protected_a5_accounting_enabled: bool
    automatic_source_posting: bool


class EclA5AccountingRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def list_actions(self) -> list[EclA5Action]:
        rows = await self._database.fetch_all(
            """
            SELECT loan_id, loan_number, loan_status, calculation_mode,
                   credit_risk_review_id, stage_label, default_label,
                   write_off_label, recovery_label, measurement_id,
                   measurement_version, measurement_date, calculation_digest,
                   measurement_status, authoritative_ecl_amount,
                   current_allowance_balance, loan_receivable_account_id,
                   loan_receivable_system_key, accrued_interest_account_id,
                   loan_component, accrued_interest_component,
                   gross_carrying_amount, writeoff_id, recovery_transaction_id,
                   recovery_amount, a5_status, protected_a5_accounting_enabled,
                   automatic_source_posting
            FROM accounting.ecl_a5_action_queue
            ORDER BY loan_number, loan_id
            """
        )
        return [EclA5Action(**dict(row)) for row in rows]

    async def post_remeasurement(
        self,
        *,
        measurement_id: UUID,
        actor_user_id: UUID,
        review_token: str,
        expected_calculation_digest: str,
        expected_prior_allowance: Decimal,
        expected_target_allowance: Decimal,
        expected_posting_date: date,
        expected_fiscal_period_id: UUID,
        expected_credit_loss_expense_account_id: UUID,
        expected_allowance_account_id: UUID,
        policy_version: str,
    ) -> UUID:
        return await self._call_id(
            """
            SELECT accounting.post_ecl_allowance_remeasurement(
                :measurement_id, :actor_user_id, :review_token,
                :expected_calculation_digest, :expected_prior_allowance,
                :expected_target_allowance, :expected_posting_date,
                :expected_fiscal_period_id,
                :expected_credit_loss_expense_account_id,
                :expected_allowance_account_id, :policy_version
            ) AS id
            """,
            locals(),
        )

    async def post_full_writeoff(self, **values: Any) -> UUID:
        return await self._call_id(
            """
            SELECT accounting.post_ecl_full_writeoff(
                :loan_id, :actor_user_id, :review_token,
                :expected_credit_risk_review_id, :expected_measurement_id,
                :expected_calculation_digest, :expected_loan_component,
                :expected_accrued_interest_component,
                :expected_gross_carrying_amount,
                :expected_allowance_balance,
                :expected_loan_receivable_account_id,
                :expected_accrued_interest_account_id,
                :expected_allowance_account_id, :expected_posting_date,
                :expected_fiscal_period_id, :policy_version
            ) AS id
            """,
            values,
        )

    async def post_recovery(self, **values: Any) -> UUID:
        return await self._call_id(
            """
            SELECT accounting.post_ecl_post_writeoff_recovery(
                :credit_risk_review_id, :actor_user_id, :review_token,
                :expected_recovery_transaction_id, :expected_recovery_amount,
                :expected_posting_date, :expected_fiscal_period_id,
                :expected_cash_account_id,
                :expected_credit_loss_expense_account_id, :policy_version
            ) AS id
            """,
            values,
        )

    async def _call_id(self, query: str, values: dict[str, Any]) -> UUID:
        try:
            row = await self._database.fetch_one(query, values)
        except Exception as exc:  # database functions are the final fail-closed boundary
            raise EclA5AccountingBlocked(str(exc)) from exc
        if row is None or row["id"] is None:
            raise EclA5AccountingBlocked("Protected A5 accounting action returned no immutable audit id.")
        return UUID(str(row["id"]))
