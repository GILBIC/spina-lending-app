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


POSTING_POLICY_VERSION = "new_loan_disbursement_journal_posting_v1"


@dataclass(frozen=True, slots=True)
class LoanDisbursementJournalPostingStatus:
    preparation_id: UUID
    disbursement_event_id: UUID
    loan_id: UUID
    client_id: UUID
    journal_entry_id: UUID
    source_event_key: str
    draft_review_token: str
    draft_policy_version: str
    posting_date: date
    fiscal_period_id: UUID
    fiscal_period_label: str
    fiscal_period_status: str
    amount: Decimal
    debit_account_id: UUID
    debit_account_system_key: str
    credit_account_id: UUID
    credit_account_system_key: str
    line_count: int
    total_debit: Decimal
    total_credit: Decimal
    journal_status: str
    entry_number: str | None
    posting_id: UUID | None
    posting_review_token: str
    posting_policy_version: str
    posted_by_user_id: UUID | None
    posted_at: datetime | None
    posting_ready: bool
    posted_audit_exact: bool
    protected_posting_enabled: bool
    automatic_source_posting_enabled: bool

    @property
    def posted(self) -> bool:
        return self.posting_id is not None and self.posted_audit_exact


class LoanDisbursementJournalPostingError(RuntimeError):
    code = "loan_disbursement_journal_posting_error"


class LoanDisbursementJournalPostingNotFound(LoanDisbursementJournalPostingError):
    code = "loan_disbursement_journal_posting_not_found"


class LoanDisbursementJournalPostingConflict(LoanDisbursementJournalPostingError):
    code = "loan_disbursement_journal_posting_conflict"


class LoanDisbursementJournalPostingValidation(LoanDisbursementJournalPostingError):
    code = "loan_disbursement_journal_posting_validation"


def _money(value: object) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _posting_review_token(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class PostgresLoanDisbursementJournalPostingRepository:
    def load_status(
        self,
        *,
        disbursement_event_id: UUID,
    ) -> LoanDisbursementJournalPostingStatus:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    row = cursor.execute(
                        """
                        select *
                        from accounting.loan_disbursement_journal_posting_status
                        where disbursement_event_id = %s
                        """,
                        (disbursement_event_id,),
                    ).fetchone()
                    if row is None:
                        raise LoanDisbursementJournalPostingNotFound(
                            "Protected new-loan disbursement journal draft was not found."
                        )
                    return self._status_from_row(row)
        except LoanDisbursementJournalPostingError:
            raise
        except psycopg.Error as error:
            raise self._map_error(error) from error

    def post(
        self,
        *,
        actor_user_id: UUID,
        disbursement_event_id: UUID,
        expected_posting_review_token: str,
    ) -> LoanDisbursementJournalPostingStatus:
        if not self._valid_token(expected_posting_review_token):
            raise LoanDisbursementJournalPostingValidation(
                "The protected new-loan disbursement posting review token is invalid."
            )

        current = self.load_status(disbursement_event_id=disbursement_event_id)
        if current.posting_review_token != expected_posting_review_token:
            raise LoanDisbursementJournalPostingConflict(
                "New-loan disbursement posting facts changed. Refresh the Management review before posting."
            )
        if not current.posting_ready and not current.posted:
            raise LoanDisbursementJournalPostingConflict(
                "Protected new-loan disbursement journal is not ready for posting."
            )

        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    row = cursor.execute(
                        """
                        select accounting.post_new_loan_disbursement_journal(
                            %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s
                        ) as posting_id
                        """,
                        (
                            current.preparation_id,
                            actor_user_id,
                            expected_posting_review_token,
                            current.journal_entry_id,
                            current.source_event_key,
                            current.draft_review_token,
                            current.posting_date,
                            current.fiscal_period_id,
                            current.debit_account_id,
                            current.credit_account_id,
                            current.amount,
                            current.total_debit,
                            current.total_credit,
                            POSTING_POLICY_VERSION,
                        ),
                    ).fetchone()
                    if row is None or row["posting_id"] is None:
                        raise LoanDisbursementJournalPostingConflict(
                            "Protected new-loan disbursement posting returned no immutable posting audit."
                        )
        except LoanDisbursementJournalPostingError:
            raise
        except psycopg.Error as error:
            raise self._map_error(error) from error

        posted = self.load_status(disbursement_event_id=disbursement_event_id)
        if not posted.posted:
            raise LoanDisbursementJournalPostingConflict(
                "Protected new-loan disbursement posting failed the immutable post-write audit review."
            )
        if posted.posting_review_token != expected_posting_review_token:
            raise LoanDisbursementJournalPostingConflict(
                "Protected new-loan disbursement posting review identity changed during posting."
            )
        return posted

    @staticmethod
    def _status_from_row(row) -> LoanDisbursementJournalPostingStatus:
        amount = _money(row["amount"])
        total_debit = _money(row["total_debit"])
        total_credit = _money(row["total_credit"])
        stored_posting_token = (
            None
            if row["posting_review_token"] is None
            else str(row["posting_review_token"])
        )
        token_payload = {
            "posting_policy_version": POSTING_POLICY_VERSION,
            "preparation_id": str(row["preparation_id"]),
            "disbursement_event_id": str(row["disbursement_event_id"]),
            "loan_id": str(row["loan_id"]),
            "client_id": str(row["client_id"]),
            "journal_entry_id": str(row["journal_entry_id"]),
            "source_event_key": str(row["source_event_key"]),
            "draft_review_token": str(row["draft_review_token"]),
            "draft_policy_version": str(row["draft_policy_version"]),
            "posting_date": row["posting_date"].isoformat(),
            "fiscal_period_id": str(row["fiscal_period_id"]),
            "debit_account_id": str(row["debit_account_id"]),
            "debit_account_system_key": str(row["debit_account_system_key"]),
            "credit_account_id": str(row["credit_account_id"]),
            "credit_account_system_key": str(row["credit_account_system_key"]),
            "amount": format(amount, ".2f"),
            "total_debit": format(total_debit, ".2f"),
            "total_credit": format(total_credit, ".2f"),
        }
        computed_posting_token = _posting_review_token(token_payload)
        if stored_posting_token is not None and stored_posting_token != computed_posting_token:
            raise LoanDisbursementJournalPostingConflict(
                "Immutable new-loan disbursement posting audit token no longer matches the posted facts."
            )

        return LoanDisbursementJournalPostingStatus(
            preparation_id=UUID(str(row["preparation_id"])),
            disbursement_event_id=UUID(str(row["disbursement_event_id"])),
            loan_id=UUID(str(row["loan_id"])),
            client_id=UUID(str(row["client_id"])),
            journal_entry_id=UUID(str(row["journal_entry_id"])),
            source_event_key=str(row["source_event_key"]),
            draft_review_token=str(row["draft_review_token"]),
            draft_policy_version=str(row["draft_policy_version"]),
            posting_date=row["posting_date"],
            fiscal_period_id=UUID(str(row["fiscal_period_id"])),
            fiscal_period_label=str(row["fiscal_period_label"]),
            fiscal_period_status=str(row["fiscal_period_status"]),
            amount=amount,
            debit_account_id=UUID(str(row["debit_account_id"])),
            debit_account_system_key=str(row["debit_account_system_key"]),
            credit_account_id=UUID(str(row["credit_account_id"])),
            credit_account_system_key=str(row["credit_account_system_key"]),
            line_count=int(row["line_count"]),
            total_debit=total_debit,
            total_credit=total_credit,
            journal_status=str(row["journal_status"]),
            entry_number=(None if row["entry_number"] is None else str(row["entry_number"])),
            posting_id=(None if row["posting_id"] is None else UUID(str(row["posting_id"]))),
            posting_review_token=computed_posting_token,
            posting_policy_version=POSTING_POLICY_VERSION,
            posted_by_user_id=(
                None
                if row["posted_by_user_id"] is None
                else UUID(str(row["posted_by_user_id"]))
            ),
            posted_at=row["posted_at"],
            posting_ready=bool(row["posting_ready"]),
            posted_audit_exact=bool(row["posted_audit_exact"]),
            protected_posting_enabled=bool(row["protected_posting_enabled"]),
            automatic_source_posting_enabled=bool(row["automatic_source_posting"]),
        )

    @staticmethod
    def _valid_token(value: str) -> bool:
        return len(value) == 64 and all(
            character in "0123456789abcdef" for character in value
        )

    @staticmethod
    def _map_error(error: psycopg.Error) -> LoanDisbursementJournalPostingError:
        message = str(error).split("CONTEXT:", 1)[0].strip()
        lowered = message.lower()
        if "was not found" in lowered:
            return LoanDisbursementJournalPostingNotFound(message)
        if any(
            marker in lowered
            for marker in (
                "changed",
                "no longer",
                "does not match",
                "already",
                "without the protected posting audit",
                "immutable",
                "not ready",
            )
        ):
            return LoanDisbursementJournalPostingConflict(message)
        if any(
            marker in lowered
            for marker in (
                "invalid",
                "must",
                "requires",
                "period",
                "account",
                "balance",
                "pattern",
                "eligible",
            )
        ):
            return LoanDisbursementJournalPostingValidation(message)
        return LoanDisbursementJournalPostingError(message)
