from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .database import open_connection


LIABILITY_POLICY = "v1_tax_additional_liability_posting_v1"
SETTLEMENT_POLICY = "v1_tax_additional_settlement_posting_v1"


class V1TaxAdditionalAmendmentError(RuntimeError):
    code = "v1_tax_additional_amendment_error"


class V1TaxAdditionalAmendmentBlocked(V1TaxAdditionalAmendmentError):
    code = "v1_tax_additional_amendment_blocked"


@dataclass(frozen=True, slots=True)
class V1TaxAdditionalAmendmentItem:
    amendment_evidence_id: UUID
    amendment_basis: str
    tax_type: str
    tax_return_id: UUID
    tax_liability_posting_id: UUID
    original_evidence_id: UUID
    replacement_evidence_id: UUID
    source_id: UUID
    loan_id: UUID
    client_id: UUID
    original_declared_tax_due: Decimal
    revised_declared_tax_due: Decimal
    original_item_tax_due: Decimal
    replacement_item_tax_due: Decimal
    additional_tax_due: Decimal
    payment_basis: str
    payment_required_amount: Decimal
    amendment_date: date
    recognition_date: date
    amendment_reference: str
    evidence_reference: str
    evidence_digest: str
    original_payment_evidence_id: UUID | None
    original_settlement_posting_id: UUID | None
    original_settlement_journal_entry_id: UUID | None
    recorded_by_user_id: UUID
    recorded_at: datetime
    liability_preparation_id: UUID | None
    liability_journal_entry_id: UUID | None
    liability_journal_status: str | None
    liability_entry_number: str | None
    liability_fiscal_period_id: UUID | None
    expense_account_code: str | None
    tax_payable_account_code: str | None
    liability_prepared_by_user_id: UUID | None
    liability_prepared_at: datetime | None
    additional_liability_posting_id: UUID | None
    liability_confirmation_digest: str | None
    liability_posted_by_user_id: UUID | None
    liability_posted_at: datetime | None
    additional_payment_evidence_id: UUID | None
    payment_date: date | None
    payment_amount: Decimal | None
    cash_account_system_key: str | None
    payment_cash_account_code: str | None
    payment_cash_account_name: str | None
    payment_reference: str | None
    payment_evidence_reference: str | None
    payment_evidence_digest: str | None
    payment_recorded_by_user_id: UUID | None
    payment_recorded_at: datetime | None
    settlement_preparation_id: UUID | None
    settlement_journal_entry_id: UUID | None
    settlement_journal_status: str | None
    settlement_entry_number: str | None
    settlement_fiscal_period_id: UUID | None
    settlement_prepared_by_user_id: UUID | None
    settlement_prepared_at: datetime | None
    additional_settlement_posting_id: UUID | None
    settlement_confirmation_digest: str | None
    settlement_posted_by_user_id: UUID | None
    settlement_posted_at: datetime | None
    amendment_status: str
    amendment_blocker: str | None
    tax_additional_amendment_enabled: bool
    tax_additional_settlement_enabled: bool
    tax_refund_credit_realization_enabled: bool
    automatic_source_posting: bool


class PostgresV1TaxAdditionalAmendmentRepository:
    _COLUMNS = """
        amendment_evidence_id, amendment_basis, tax_type, tax_return_id,
        tax_liability_posting_id, original_evidence_id, replacement_evidence_id,
        source_id, loan_id, client_id, original_declared_tax_due,
        revised_declared_tax_due, original_item_tax_due, replacement_item_tax_due,
        additional_tax_due, payment_basis, payment_required_amount,
        amendment_date, recognition_date, amendment_reference,
        evidence_reference, evidence_digest, original_payment_evidence_id,
        original_settlement_posting_id, original_settlement_journal_entry_id,
        recorded_by_user_id, recorded_at, liability_preparation_id,
        liability_journal_entry_id, liability_journal_status,
        liability_entry_number, liability_fiscal_period_id, expense_account_code,
        tax_payable_account_code, liability_prepared_by_user_id,
        liability_prepared_at, additional_liability_posting_id,
        liability_confirmation_digest, liability_posted_by_user_id,
        liability_posted_at, additional_payment_evidence_id, payment_date,
        payment_amount, cash_account_system_key, payment_cash_account_code,
        payment_cash_account_name, payment_reference, payment_evidence_reference,
        payment_evidence_digest, payment_recorded_by_user_id, payment_recorded_at,
        settlement_preparation_id, settlement_journal_entry_id,
        settlement_journal_status, settlement_entry_number,
        settlement_fiscal_period_id, settlement_prepared_by_user_id,
        settlement_prepared_at, additional_settlement_posting_id,
        settlement_confirmation_digest, settlement_posted_by_user_id,
        settlement_posted_at, amendment_status, amendment_blocker,
        tax_additional_amendment_enabled, tax_additional_settlement_enabled,
        tax_refund_credit_realization_enabled, automatic_source_posting
    """

    def list_items(
        self, *, status: str = "all", limit: int = 100, offset: int = 0
    ) -> tuple[V1TaxAdditionalAmendmentItem, ...]:
        where = self._status_where(status)
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    SELECT {self._COLUMNS}
                    FROM accounting.v1_tax_additional_amendment_queue
                    WHERE {where}
                    ORDER BY amendment_date DESC, recorded_at DESC,
                             amendment_evidence_id
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
                return tuple(
                    V1TaxAdditionalAmendmentItem(**dict(row))
                    for row in cursor.fetchall()
                )

    def get_item(self, amendment_evidence_id: UUID) -> V1TaxAdditionalAmendmentItem:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    SELECT {self._COLUMNS}
                    FROM accounting.v1_tax_additional_amendment_queue
                    WHERE amendment_evidence_id=%s
                    """,
                    (amendment_evidence_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise V1TaxAdditionalAmendmentBlocked(
                        "V1 additional-tax amendment evidence item was not found."
                    )
                return V1TaxAdditionalAmendmentItem(**dict(row))

    def summary(self) -> dict[str, object]:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    "SELECT * FROM accounting.v1_tax_additional_amendment_summary"
                )
                row = cursor.fetchone()
                if row is None:
                    raise V1TaxAdditionalAmendmentError(
                        "V1 additional-tax amendment summary is unavailable."
                    )
                return dict(row)

    def record_amendment_evidence(
        self,
        *,
        actor_user_id: UUID,
        idempotency_key: UUID,
        tax_return_id: UUID,
        tax_liability_posting_id: UUID,
        replacement_evidence_id: UUID,
        amendment_basis: str,
        amendment_date: date,
        recognition_date: date,
        amendment_reference: str,
        evidence_reference: str,
        evidence_digest: str,
        evidence_note: str,
    ) -> UUID:
        return self._call_id(
            """
            SELECT accounting.record_v1_tax_additional_amendment_evidence(
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
            ) AS id
            """,
            (
                actor_user_id,
                idempotency_key,
                tax_return_id,
                tax_liability_posting_id,
                replacement_evidence_id,
                amendment_basis,
                amendment_date,
                recognition_date,
                amendment_reference,
                evidence_reference,
                evidence_digest,
                evidence_note,
            ),
        )

    def prepare_liability(
        self, *, amendment_evidence_id: UUID, actor_user_id: UUID
    ) -> UUID:
        return self._call_id(
            "SELECT accounting.prepare_v1_tax_additional_liability_journal(%s,%s) AS id",
            (amendment_evidence_id, actor_user_id),
        )

    def post_liability(
        self,
        *,
        amendment_evidence_id: UUID,
        actor_user_id: UUID,
        confirmation_token: str,
        expected_evidence_digest: str,
        expected_original_declared_tax_due: Decimal,
        expected_revised_declared_tax_due: Decimal,
        expected_original_item_tax_due: Decimal,
        expected_replacement_item_tax_due: Decimal,
        expected_additional_tax_due: Decimal,
        expected_expense_account_code: str,
        expected_tax_payable_account_code: str,
        expected_posting_date: date,
        expected_fiscal_period_id: UUID,
        policy_version: str = LIABILITY_POLICY,
    ) -> UUID:
        return self._call_id(
            """
            SELECT accounting.post_v1_tax_additional_liability_journal(
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
            ) AS id
            """,
            (
                amendment_evidence_id,
                actor_user_id,
                confirmation_token,
                expected_evidence_digest,
                expected_original_declared_tax_due,
                expected_revised_declared_tax_due,
                expected_original_item_tax_due,
                expected_replacement_item_tax_due,
                expected_additional_tax_due,
                expected_expense_account_code,
                expected_tax_payable_account_code,
                expected_posting_date,
                expected_fiscal_period_id,
                policy_version,
            ),
        )

    def record_payment_evidence(
        self,
        *,
        actor_user_id: UUID,
        idempotency_key: UUID,
        amendment_evidence_id: UUID,
        payment_date: date,
        payment_amount: Decimal,
        cash_account_system_key: str,
        payment_reference: str,
        evidence_reference: str,
        evidence_digest: str,
        evidence_note: str,
    ) -> UUID:
        return self._call_id(
            """
            SELECT accounting.record_v1_tax_additional_payment_evidence(
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s
            ) AS id
            """,
            (
                actor_user_id,
                idempotency_key,
                amendment_evidence_id,
                payment_date,
                payment_amount,
                cash_account_system_key,
                payment_reference,
                evidence_reference,
                evidence_digest,
                evidence_note,
            ),
        )

    def prepare_settlement(
        self, *, payment_evidence_id: UUID, actor_user_id: UUID
    ) -> UUID:
        return self._call_id(
            "SELECT accounting.prepare_v1_tax_additional_settlement_journal(%s,%s) AS id",
            (payment_evidence_id, actor_user_id),
        )

    def post_settlement(
        self,
        *,
        payment_evidence_id: UUID,
        actor_user_id: UUID,
        confirmation_token: str,
        expected_amendment_evidence_digest: str,
        expected_additional_liability_confirmation_digest: str,
        expected_payment_evidence_digest: str,
        expected_payment_amount: Decimal,
        expected_tax_payable_account_code: str,
        expected_cash_account_code: str,
        expected_posting_date: date,
        expected_fiscal_period_id: UUID,
        policy_version: str = SETTLEMENT_POLICY,
    ) -> UUID:
        return self._call_id(
            """
            SELECT accounting.post_v1_tax_additional_settlement_journal(
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
            ) AS id
            """,
            (
                payment_evidence_id,
                actor_user_id,
                confirmation_token,
                expected_amendment_evidence_digest,
                expected_additional_liability_confirmation_digest,
                expected_payment_evidence_digest,
                expected_payment_amount,
                expected_tax_payable_account_code,
                expected_cash_account_code,
                expected_posting_date,
                expected_fiscal_period_id,
                policy_version,
            ),
        )

    @staticmethod
    def _status_where(status: str) -> str:
        clauses = {
            "all": "true",
            "ready": "amendment_status = 'amendment_evidence_ready'",
            "liability_prepared": "amendment_status = 'additional_liability_prepared'",
            "awaiting_payment": "amendment_status = 'additional_liability_posted_awaiting_payment'",
            "payment_ready": "amendment_status = 'additional_payment_evidence_ready'",
            "settlement_prepared": "amendment_status = 'additional_settlement_prepared'",
            "settled": "amendment_status = 'additional_tax_settled'",
            "review": "amendment_status LIKE '%review_required'",
            "blocked": "amendment_status LIKE 'blocked_%'",
        }
        clause = clauses.get(status)
        if clause is None:
            raise ValueError("Unsupported V1 additional-tax amendment status filter.")
        return clause

    @staticmethod
    def _call_id(query: str, params: tuple[object, ...]) -> UUID:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(query, params)
                    row = cursor.fetchone()
                    if row is None or row["id"] is None:
                        raise V1TaxAdditionalAmendmentBlocked(
                            "Protected V1 additional-tax amendment action returned no immutable identifier."
                        )
                    result = UUID(str(row["id"]))
                connection.commit()
                return result
        except V1TaxAdditionalAmendmentError:
            raise
        except psycopg.Error as exc:
            message = str(exc).split("CONTEXT:", 1)[0].strip()
            raise V1TaxAdditionalAmendmentBlocked(message) from exc
