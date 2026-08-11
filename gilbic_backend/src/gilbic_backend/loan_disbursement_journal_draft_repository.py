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


COORDINATE_POLICY_VERSION = "new_loan_disbursement_coordinates_v1"
DRAFT_POLICY_VERSION = "new_loan_disbursement_journal_draft_v1"


@dataclass(frozen=True, slots=True)
class LoanDisbursementJournalDraftReview:
    disbursement_event_id: UUID
    loan_id: UUID
    loan_number: str
    client_id: UUID
    client_code: str
    client_name: str
    posting_date: date
    fiscal_period_id: UUID
    source_event_key: str
    external_reference: str
    debit_account_id: UUID
    debit_account_system_key: str
    debit_amount: Decimal
    credit_account_id: UUID
    credit_account_system_key: str
    credit_amount: Decimal
    initial_measurement_basis: str
    coordinate_policy_version: str
    draft_policy_version: str
    review_token: str
    posting_enabled: bool = False
    automatic_source_posting_enabled: bool = False


@dataclass(frozen=True, slots=True)
class LoanDisbursementJournalDraftStatus:
    preparation_id: UUID
    disbursement_event_id: UUID
    loan_id: UUID
    client_id: UUID
    journal_entry_id: UUID
    source_event_key: str
    review_token: str
    coordinate_policy_version: str
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
    journal_status: str
    entry_number: str | None
    prepared_by_user_id: UUID
    prepared_at: datetime
    line_count: int
    total_debit: Decimal
    total_credit: Decimal
    draft_integrity_ready: bool
    posting_enabled: bool
    automatic_source_posting_enabled: bool


class LoanDisbursementJournalDraftError(RuntimeError):
    code = "loan_disbursement_journal_draft_error"


class LoanDisbursementJournalDraftNotFound(LoanDisbursementJournalDraftError):
    code = "loan_disbursement_journal_draft_not_found"


class LoanDisbursementJournalDraftConflict(LoanDisbursementJournalDraftError):
    code = "loan_disbursement_journal_draft_conflict"


class LoanDisbursementJournalDraftValidation(LoanDisbursementJournalDraftError):
    code = "loan_disbursement_journal_draft_validation"


def _money(value: object) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _review_token(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class PostgresLoanDisbursementJournalDraftRepository:
    def load_review(
        self,
        *,
        disbursement_event_id: UUID,
    ) -> LoanDisbursementJournalDraftReview:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    row = cursor.execute(
                        """
                        select *
                        from accounting.loan_disbursement_journal_coordinates
                        where disbursement_event_id = %s
                        """,
                        (disbursement_event_id,),
                    ).fetchone()
                    if row is None:
                        raise LoanDisbursementJournalDraftNotFound(
                            "Authoritative loan-disbursement evidence was not found."
                        )
                    return self._review_from_coordinate(row)
        except LoanDisbursementJournalDraftError:
            raise
        except psycopg.Error as error:
            raise self._map_error(error) from error

    def load_status(
        self,
        *,
        disbursement_event_id: UUID,
    ) -> LoanDisbursementJournalDraftStatus | None:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    row = cursor.execute(
                        """
                        select *
                        from accounting.loan_disbursement_journal_draft_status
                        where disbursement_event_id = %s
                        """,
                        (disbursement_event_id,),
                    ).fetchone()
                    return None if row is None else self._status_from_row(row)
        except psycopg.Error as error:
            raise self._map_error(error) from error

    def prepare(
        self,
        *,
        actor_user_id: UUID,
        disbursement_event_id: UUID,
        expected_review_token: str,
    ) -> LoanDisbursementJournalDraftStatus:
        if (
            len(expected_review_token) != 64
            or any(character not in "0123456789abcdef" for character in expected_review_token)
        ):
            raise LoanDisbursementJournalDraftValidation(
                "The protected new-loan disbursement review token is invalid."
            )

        # Exact retry remains possible after Stage 5D.20 intentionally changes
        # from coordinate_ready to journal_history_exists. The immutable Stage
        # 5D.21 preparation becomes the retry proof.
        existing = self.load_status(disbursement_event_id=disbursement_event_id)
        if existing is not None:
            if existing.review_token != expected_review_token:
                raise LoanDisbursementJournalDraftConflict(
                    "An existing protected draft was created from a different reviewed confirmation."
                )
            if not existing.draft_integrity_ready:
                raise LoanDisbursementJournalDraftConflict(
                    "The existing protected new-loan disbursement draft failed immutable integrity review."
                )
            return existing

        initial = self.load_review(disbursement_event_id=disbursement_event_id)
        if initial.review_token != expected_review_token:
            raise LoanDisbursementJournalDraftConflict(
                "New-loan disbursement coordinates changed. Refresh the Management review before preparing a protected draft."
            )

        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    row = cursor.execute(
                        """
                        select accounting.create_new_loan_disbursement_journal_draft(
                            %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s
                        ) as preparation_id
                        """,
                        (
                            disbursement_event_id,
                            actor_user_id,
                            expected_review_token,
                            initial.source_event_key,
                            initial.posting_date,
                            initial.fiscal_period_id,
                            initial.debit_account_id,
                            initial.credit_account_id,
                            initial.debit_amount,
                            COORDINATE_POLICY_VERSION,
                            DRAFT_POLICY_VERSION,
                        ),
                    ).fetchone()
                    if row is None or row["preparation_id"] is None:
                        raise LoanDisbursementJournalDraftConflict(
                            "Protected new-loan disbursement draft preparation returned no immutable preparation record."
                        )

                    status_row = cursor.execute(
                        """
                        select *
                        from accounting.loan_disbursement_journal_draft_status
                        where preparation_id = %s
                        """,
                        (row["preparation_id"],),
                    ).fetchone()
                    if status_row is None:
                        raise LoanDisbursementJournalDraftConflict(
                            "Protected new-loan disbursement draft status was not found after preparation."
                        )
                    status = self._status_from_row(status_row)
                    if not status.draft_integrity_ready:
                        raise LoanDisbursementJournalDraftConflict(
                            "Protected new-loan disbursement draft failed the post-create integrity check."
                        )
                    if status.review_token != expected_review_token:
                        raise LoanDisbursementJournalDraftConflict(
                            "Protected new-loan disbursement draft review identity changed during preparation."
                        )
                    return status
        except LoanDisbursementJournalDraftError:
            raise
        except psycopg.Error as error:
            raise self._map_error(error) from error

    @staticmethod
    def _review_from_coordinate(row) -> LoanDisbursementJournalDraftReview:
        coordinate_status = str(row["coordinate_status"])
        if coordinate_status != "coordinate_ready":
            raise LoanDisbursementJournalDraftValidation(
                f"New-loan disbursement coordinate is blocked: {coordinate_status}."
            )
        if bool(row["journal_draft_enabled"]) or bool(row["automatic_source_posting"]):
            raise LoanDisbursementJournalDraftValidation(
                "Stage 5D.20 safety flags unexpectedly enable drafting or automatic posting."
            )
        if str(row["event_kind"]) != "new_loan_release" or str(row["calculation_mode"]) != "fixed_daily":
            raise LoanDisbursementJournalDraftValidation(
                "Protected Stage 5D.21 drafting supports only a pure new Regular fixed-daily release."
            )

        amount = _money(row["debit_amount"])
        credit_amount = _money(row["credit_amount"])
        if amount <= 0 or amount != credit_amount:
            raise LoanDisbursementJournalDraftValidation(
                "Protected new-loan disbursement coordinates are not exactly balanced."
            )

        token_payload = {
            "coordinate_policy_version": COORDINATE_POLICY_VERSION,
            "draft_policy_version": DRAFT_POLICY_VERSION,
            "disbursement_event_id": str(row["disbursement_event_id"]),
            "loan_id": str(row["loan_id"]),
            "client_id": str(row["client_id"]),
            "source_event_key": str(row["source_event_key"]),
            "posting_date": row["posting_date"].isoformat(),
            "fiscal_period_id": str(row["fiscal_period_id"]),
            "debit_account_id": str(row["debit_account_id"]),
            "debit_account_system_key": str(row["debit_account_system_key"]),
            "debit_amount": format(amount, ".2f"),
            "credit_account_id": str(row["credit_account_id"]),
            "credit_account_system_key": str(row["credit_account_system_key"]),
            "credit_amount": format(credit_amount, ".2f"),
            "external_reference": str(row["external_reference"]),
            "initial_measurement_basis": str(row["initial_measurement_basis"]),
        }
        review_token = _review_token(token_payload)

        return LoanDisbursementJournalDraftReview(
            disbursement_event_id=UUID(str(row["disbursement_event_id"])),
            loan_id=UUID(str(row["loan_id"])),
            loan_number=str(row["loan_number"]),
            client_id=UUID(str(row["client_id"])),
            client_code=str(row["client_code"]),
            client_name=str(row["client_name"]),
            posting_date=row["posting_date"],
            fiscal_period_id=UUID(str(row["fiscal_period_id"])),
            source_event_key=str(row["source_event_key"]),
            external_reference=str(row["external_reference"]),
            debit_account_id=UUID(str(row["debit_account_id"])),
            debit_account_system_key=str(row["debit_account_system_key"]),
            debit_amount=amount,
            credit_account_id=UUID(str(row["credit_account_id"])),
            credit_account_system_key=str(row["credit_account_system_key"]),
            credit_amount=credit_amount,
            initial_measurement_basis=str(row["initial_measurement_basis"]),
            coordinate_policy_version=COORDINATE_POLICY_VERSION,
            draft_policy_version=DRAFT_POLICY_VERSION,
            review_token=review_token,
        )

    @staticmethod
    def _status_from_row(row) -> LoanDisbursementJournalDraftStatus:
        return LoanDisbursementJournalDraftStatus(
            preparation_id=UUID(str(row["preparation_id"])),
            disbursement_event_id=UUID(str(row["disbursement_event_id"])),
            loan_id=UUID(str(row["loan_id"])),
            client_id=UUID(str(row["client_id"])),
            journal_entry_id=UUID(str(row["journal_entry_id"])),
            source_event_key=str(row["source_event_key"]),
            review_token=str(row["review_token"]),
            coordinate_policy_version=str(row["coordinate_policy_version"]),
            draft_policy_version=str(row["draft_policy_version"]),
            posting_date=row["posting_date"],
            fiscal_period_id=UUID(str(row["fiscal_period_id"])),
            fiscal_period_label=str(row["fiscal_period_label"]),
            fiscal_period_status=str(row["fiscal_period_status"]),
            amount=_money(row["amount"]),
            debit_account_id=UUID(str(row["debit_account_id"])),
            debit_account_system_key=str(row["debit_account_system_key"]),
            credit_account_id=UUID(str(row["credit_account_id"])),
            credit_account_system_key=str(row["credit_account_system_key"]),
            journal_status=str(row["journal_status"]),
            entry_number=(None if row["entry_number"] is None else str(row["entry_number"])),
            prepared_by_user_id=UUID(str(row["prepared_by_user_id"])),
            prepared_at=row["prepared_at"],
            line_count=int(row["line_count"]),
            total_debit=_money(row["total_debit"]),
            total_credit=_money(row["total_credit"]),
            draft_integrity_ready=bool(row["draft_integrity_ready"]),
            posting_enabled=bool(row["posting_enabled"]),
            automatic_source_posting_enabled=bool(row["automatic_source_posting"]),
        )

    @staticmethod
    def _map_error(error: psycopg.Error) -> LoanDisbursementJournalDraftError:
        message = str(error).split("CONTEXT:", 1)[0].strip()
        lowered = message.lower()
        if "not found" in lowered:
            return LoanDisbursementJournalDraftNotFound(message)
        if any(
            marker in lowered
            for marker in (
                "changed",
                "already exists",
                "existing protected",
                "integrity",
                "journal history",
                "different reviewed",
            )
        ):
            return LoanDisbursementJournalDraftConflict(message)
        return LoanDisbursementJournalDraftValidation(message)
