from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .database import open_connection


REVERSAL_POLICY_VERSION = "new_loan_disbursement_cancellation_reversal_v1"


@dataclass(frozen=True, slots=True)
class LoanDisbursementCancellationStatus:
    posting_id: UUID
    preparation_id: UUID
    disbursement_event_id: UUID
    loan_id: UUID
    client_id: UUID
    original_journal_entry_id: UUID
    original_entry_number: str
    original_source_event_key: str
    posting_review_token: str
    amount: Decimal
    original_debit_account_id: UUID
    original_debit_account_system_key: str
    original_credit_account_id: UUID
    original_credit_account_system_key: str
    original_journal_status: str
    cancellation_id: UUID | None
    cancellation_source_key: str | None
    reversal_posting_date: date | None
    cancellation_reason: str | None
    cancelled_by_user_id: UUID | None
    cancelled_at: datetime | None
    reversal_id: UUID | None
    reversal_journal_entry_id: UUID | None
    reversal_entry_number: str | None
    reversal_source_event_key: str | None
    reversal_journal_status: str | None
    cancellation_ready: bool
    cancelled_reversal_audit_exact: bool
    protected_reversal_enabled: bool
    automatic_source_posting_enabled: bool
    cancellation_review_token: str

    @property
    def cancelled(self) -> bool:
        return self.cancellation_id is not None and self.cancelled_reversal_audit_exact


class LoanDisbursementCancellationError(RuntimeError):
    code = "loan_disbursement_cancellation_error"


class LoanDisbursementCancellationNotFound(LoanDisbursementCancellationError):
    code = "loan_disbursement_cancellation_not_found"


class LoanDisbursementCancellationConflict(LoanDisbursementCancellationError):
    code = "loan_disbursement_cancellation_conflict"


class LoanDisbursementCancellationValidation(LoanDisbursementCancellationError):
    code = "loan_disbursement_cancellation_validation"


def _money(value: object) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _review_token(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class PostgresLoanDisbursementCancellationRepository:
    def load_status(
        self,
        *,
        disbursement_event_id: UUID,
    ) -> LoanDisbursementCancellationStatus:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    row = cursor.execute(
                        """
                        select *
                        from accounting.loan_disbursement_cancellation_status
                        where disbursement_event_id = %s
                        """,
                        (disbursement_event_id,),
                    ).fetchone()
                    if row is None:
                        raise LoanDisbursementCancellationNotFound(
                            "Posted protected new-loan disbursement journal was not found."
                        )
                    return self._status_from_row(row)
        except LoanDisbursementCancellationError:
            raise
        except psycopg.Error as error:
            raise self._map_error(error) from error

    def reverse(
        self,
        *,
        actor_user_id: UUID,
        disbursement_event_id: UUID,
        expected_cancellation_review_token: str,
        reversal_posting_date: date,
        reason: str,
    ) -> LoanDisbursementCancellationStatus:
        normalized_reason = reason.strip()
        if len(normalized_reason) < 3:
            raise LoanDisbursementCancellationValidation(
                "Enter a clear reason for cancelling and reversing the new-loan disbursement."
            )
        if not self._valid_token(expected_cancellation_review_token):
            raise LoanDisbursementCancellationValidation(
                "The protected new-loan disbursement cancellation review token is invalid."
            )

        current = self.load_status(disbursement_event_id=disbursement_event_id)
        if current.cancellation_review_token != expected_cancellation_review_token:
            raise LoanDisbursementCancellationConflict(
                "Posted new-loan disbursement facts changed. Refresh the Management cancellation review."
            )
        if not current.cancellation_ready and not current.cancelled:
            raise LoanDisbursementCancellationConflict(
                "Protected new-loan disbursement posting is not ready for controlled cancellation/reversal."
            )

        # Exact retry must repeat the original immutable actor/date/reason.
        if current.cancelled:
            if current.cancelled_by_user_id != actor_user_id:
                raise LoanDisbursementCancellationConflict(
                    "Existing protected cancellation was performed by a different Management actor."
                )
            if current.reversal_posting_date != reversal_posting_date:
                raise LoanDisbursementCancellationConflict(
                    "Existing protected cancellation has a different reversal posting date."
                )
            if (current.cancellation_reason or "") != normalized_reason:
                raise LoanDisbursementCancellationConflict(
                    "Existing protected cancellation has a different reason."
                )

        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    row = cursor.execute(
                        """
                        select accounting.reverse_posted_new_loan_disbursement(
                            %s, %s, %s, %s
                        ) as cancellation_id
                        """,
                        (
                            current.posting_id,
                            actor_user_id,
                            reversal_posting_date,
                            normalized_reason,
                        ),
                    ).fetchone()
                    if row is None or row["cancellation_id"] is None:
                        raise LoanDisbursementCancellationConflict(
                            "Protected new-loan disbursement cancellation returned no immutable cancellation record."
                        )
        except LoanDisbursementCancellationError:
            raise
        except psycopg.Error as error:
            raise self._map_error(error) from error

        cancelled = self.load_status(disbursement_event_id=disbursement_event_id)
        if not cancelled.cancelled:
            raise LoanDisbursementCancellationConflict(
                "Protected new-loan disbursement cancellation failed the immutable reversal-audit review."
            )
        if cancelled.cancellation_review_token != expected_cancellation_review_token:
            raise LoanDisbursementCancellationConflict(
                "Protected new-loan disbursement cancellation review identity changed during reversal."
            )
        return cancelled

    @staticmethod
    def _status_from_row(row) -> LoanDisbursementCancellationStatus:
        amount = _money(row["amount"])
        token_payload = {
            "reversal_policy_version": REVERSAL_POLICY_VERSION,
            "posting_id": str(row["posting_id"]),
            "preparation_id": str(row["preparation_id"]),
            "disbursement_event_id": str(row["disbursement_event_id"]),
            "loan_id": str(row["loan_id"]),
            "client_id": str(row["client_id"]),
            "original_journal_entry_id": str(row["original_journal_entry_id"]),
            "original_entry_number": str(row["original_entry_number"]),
            "original_source_event_key": str(row["original_source_event_key"]),
            "posting_review_token": str(row["posting_review_token"]),
            "amount": format(amount, ".2f"),
            "original_debit_account_id": str(row["original_debit_account_id"]),
            "original_debit_account_system_key": str(
                row["original_debit_account_system_key"]
            ),
            "original_credit_account_id": str(row["original_credit_account_id"]),
            "original_credit_account_system_key": str(
                row["original_credit_account_system_key"]
            ),
        }
        cancellation_review_token = _review_token(token_payload)

        return LoanDisbursementCancellationStatus(
            posting_id=UUID(str(row["posting_id"])),
            preparation_id=UUID(str(row["preparation_id"])),
            disbursement_event_id=UUID(str(row["disbursement_event_id"])),
            loan_id=UUID(str(row["loan_id"])),
            client_id=UUID(str(row["client_id"])),
            original_journal_entry_id=UUID(str(row["original_journal_entry_id"])),
            original_entry_number=str(row["original_entry_number"]),
            original_source_event_key=str(row["original_source_event_key"]),
            posting_review_token=str(row["posting_review_token"]),
            amount=amount,
            original_debit_account_id=UUID(str(row["original_debit_account_id"])),
            original_debit_account_system_key=str(
                row["original_debit_account_system_key"]
            ),
            original_credit_account_id=UUID(str(row["original_credit_account_id"])),
            original_credit_account_system_key=str(
                row["original_credit_account_system_key"]
            ),
            original_journal_status=str(row["original_journal_status"]),
            cancellation_id=(
                None if row["cancellation_id"] is None else UUID(str(row["cancellation_id"]))
            ),
            cancellation_source_key=(
                None
                if row["cancellation_source_key"] is None
                else str(row["cancellation_source_key"])
            ),
            reversal_posting_date=row["reversal_posting_date"],
            cancellation_reason=(
                None if row["cancellation_reason"] is None else str(row["cancellation_reason"])
            ),
            cancelled_by_user_id=(
                None
                if row["cancelled_by_user_id"] is None
                else UUID(str(row["cancelled_by_user_id"]))
            ),
            cancelled_at=row["cancelled_at"],
            reversal_id=(None if row["reversal_id"] is None else UUID(str(row["reversal_id"]))),
            reversal_journal_entry_id=(
                None
                if row["reversal_journal_entry_id"] is None
                else UUID(str(row["reversal_journal_entry_id"]))
            ),
            reversal_entry_number=(
                None
                if row["reversal_entry_number"] is None
                else str(row["reversal_entry_number"])
            ),
            reversal_source_event_key=(
                None
                if row["reversal_source_event_key"] is None
                else str(row["reversal_source_event_key"])
            ),
            reversal_journal_status=(
                None
                if row["reversal_journal_status"] is None
                else str(row["reversal_journal_status"])
            ),
            cancellation_ready=bool(row["cancellation_ready"]),
            cancelled_reversal_audit_exact=bool(row["cancelled_reversal_audit_exact"]),
            protected_reversal_enabled=bool(row["protected_reversal_enabled"]),
            automatic_source_posting_enabled=bool(row["automatic_source_posting"]),
            cancellation_review_token=cancellation_review_token,
        )

    @staticmethod
    def _valid_token(value: str) -> bool:
        return len(value) == 64 and all(
            character in "0123456789abcdef" for character in value
        )

    @staticmethod
    def _map_error(error: psycopg.Error) -> LoanDisbursementCancellationError:
        message = str(error).split("CONTEXT:", 1)[0].strip()
        lowered = message.lower()
        if "was not found" in lowered:
            return LoanDisbursementCancellationNotFound(message)
        if any(
            marker in lowered
            for marker in (
                "changed",
                "no longer",
                "does not match",
                "already",
                "inconsistent",
                "outside this cancellation audit",
                "different",
            )
        ):
            return LoanDisbursementCancellationConflict(message)
        if any(
            marker in lowered
            for marker in (
                "requires",
                "required",
                "reason",
                "period",
                "account",
                "eligible",
                "integrity",
            )
        ):
            return LoanDisbursementCancellationValidation(message)
        return LoanDisbursementCancellationError(message)
