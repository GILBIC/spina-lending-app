from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .database import open_connection


DRAFT_POLICY_VERSION = "seven_by_seven_source_event_journal_draft_v1"


@dataclass(frozen=True, slots=True)
class SevenBySevenJournalCoordinate:
    line_number: int
    journal_component: str
    account_id: UUID
    account_code: str
    account_system_key: str
    account_name: str
    debit: Decimal
    credit: Decimal


@dataclass(frozen=True, slots=True)
class SevenBySevenJournalDraftReview:
    transaction_id: UUID
    loan_id: UUID
    loan_number: str
    client_id: UUID
    client_code: str
    client_name: str
    posting_date: date
    fiscal_period_id: UUID
    source_event_key: str
    source_event_review_token: str
    coordinate_digest: str
    source_cash_amount: Decimal
    eir_interest_accrual: Decimal
    accounting_eir_interest_received: Decimal
    accounting_7x7_principal_received: Decimal
    coordinate_line_count: int
    total_debit: Decimal
    total_credit: Decimal
    draft_policy_version: str
    coordinates: tuple[SevenBySevenJournalCoordinate, ...]
    draft_review_ready: bool
    posting_enabled: bool = False
    automatic_source_posting_enabled: bool = False


@dataclass(frozen=True, slots=True)
class SevenBySevenJournalDraftStatus:
    preparation_id: UUID
    transaction_id: UUID
    loan_id: UUID
    client_id: UUID
    journal_entry_id: UUID
    source_event_key: str
    source_event_review_token: str
    coordinate_digest: str
    draft_policy_version: str
    posting_date: date
    fiscal_period_id: UUID
    fiscal_period_label: str
    fiscal_period_status: str
    source_cash_amount: Decimal
    eir_interest_accrual: Decimal
    accounting_eir_interest_received: Decimal
    accounting_7x7_principal_received: Decimal
    coordinate_line_count: int
    prepared_total_debit: Decimal
    prepared_total_credit: Decimal
    prepared_by_user_id: UUID
    prepared_at: datetime
    journal_status: str
    entry_number: str | None
    line_count: int
    total_debit: Decimal
    total_credit: Decimal
    draft_integrity_ready: bool
    posting_enabled: bool = False
    automatic_source_posting_enabled: bool = False


class SevenBySevenJournalDraftError(RuntimeError):
    code = "seven_by_seven_journal_draft_error"


class SevenBySevenJournalDraftNotFound(SevenBySevenJournalDraftError):
    code = "seven_by_seven_journal_draft_not_found"


class SevenBySevenJournalDraftConflict(SevenBySevenJournalDraftError):
    code = "seven_by_seven_journal_draft_conflict"


class SevenBySevenJournalDraftValidation(SevenBySevenJournalDraftError):
    code = "seven_by_seven_journal_draft_validation"


def _money(value: object) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _token(value: str, *, label: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) != 64 or any(character not in "0123456789abcdef" for character in normalized):
        raise SevenBySevenJournalDraftValidation(f"The protected 7x7 {label} is invalid.")
    return normalized


class PostgresSevenBySevenJournalDraftRepository:
    def load_review(self, *, transaction_id: UUID) -> SevenBySevenJournalDraftReview:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    row = cursor.execute(
                        """
                        select *
                        from accounting.seven_by_seven_journal_draft_review
                        where transaction_id = %s
                        """,
                        (transaction_id,),
                    ).fetchone()
                    if row is None:
                        raise SevenBySevenJournalDraftNotFound(
                            "Current protected 7x7 source-event review was not found."
                        )
                    coordinates = cursor.execute(
                        """
                        select line_number, journal_component, account_id, account_code,
                               account_system_key, account_name, debit, credit
                        from accounting.seven_by_seven_source_event_journal_coordinate_preview
                        where transaction_id = %s and coordinate_preview_ready
                        order by line_number
                        """,
                        (transaction_id,),
                    ).fetchall()
                    return self._review_from_rows(row, coordinates)
        except SevenBySevenJournalDraftError:
            raise
        except psycopg.Error as error:
            raise self._map_error(error) from error

    def load_status(self, *, transaction_id: UUID) -> SevenBySevenJournalDraftStatus | None:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    row = cursor.execute(
                        """
                        select *
                        from accounting.seven_by_seven_journal_draft_status
                        where transaction_id = %s
                        """,
                        (transaction_id,),
                    ).fetchone()
                    return None if row is None else self._status_from_row(row)
        except psycopg.Error as error:
            raise self._map_error(error) from error

    def prepare(
        self,
        *,
        actor_user_id: UUID,
        transaction_id: UUID,
        expected_review_token: str,
        expected_coordinate_digest: str,
    ) -> SevenBySevenJournalDraftStatus:
        review_token = _token(expected_review_token, label="source-event review token")
        coordinate_digest = _token(expected_coordinate_digest, label="coordinate digest")

        existing = self.load_status(transaction_id=transaction_id)
        if existing is not None:
            if (
                existing.source_event_review_token != review_token
                or existing.coordinate_digest != coordinate_digest
            ):
                raise SevenBySevenJournalDraftConflict(
                    "An existing protected 7x7 draft was created from a different reviewed confirmation."
                )
            if not existing.draft_integrity_ready:
                raise SevenBySevenJournalDraftConflict(
                    "The existing protected 7x7 draft failed stale-safe integrity review."
                )
            return existing

        review = self.load_review(transaction_id=transaction_id)
        if review.source_event_review_token != review_token or review.coordinate_digest != coordinate_digest:
            raise SevenBySevenJournalDraftConflict(
                "Protected 7x7 source evidence or journal coordinates changed. Refresh Management review."
            )
        if not review.draft_review_ready:
            raise SevenBySevenJournalDraftValidation(
                "The protected 7x7 source event is not ready for journal-draft preparation."
            )

        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    created = cursor.execute(
                        """
                        select accounting.create_seven_by_seven_journal_draft(
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        ) as preparation_id
                        """,
                        (
                            transaction_id,
                            actor_user_id,
                            review_token,
                            coordinate_digest,
                            review.source_event_key,
                            review.posting_date,
                            review.fiscal_period_id,
                            review.source_cash_amount,
                            review.total_debit,
                            review.total_credit,
                            DRAFT_POLICY_VERSION,
                        ),
                    ).fetchone()
                    if created is None or created["preparation_id"] is None:
                        raise SevenBySevenJournalDraftConflict(
                            "Protected 7x7 draft preparation returned no immutable preparation record."
                        )
                    status_row = cursor.execute(
                        """
                        select * from accounting.seven_by_seven_journal_draft_status
                        where preparation_id = %s
                        """,
                        (created["preparation_id"],),
                    ).fetchone()
                    if status_row is None:
                        raise SevenBySevenJournalDraftConflict(
                            "Protected 7x7 draft status was not found after preparation."
                        )
                    status = self._status_from_row(status_row)
                    if not status.draft_integrity_ready:
                        raise SevenBySevenJournalDraftConflict(
                            "Protected 7x7 draft failed post-create stale-safe integrity review."
                        )
                    if (
                        status.source_event_review_token != review_token
                        or status.coordinate_digest != coordinate_digest
                    ):
                        raise SevenBySevenJournalDraftConflict(
                            "Protected 7x7 review identity changed during draft preparation."
                        )
                    return status
        except SevenBySevenJournalDraftError:
            raise
        except psycopg.Error as error:
            raise self._map_error(error) from error

    @staticmethod
    def _review_from_rows(row, coordinate_rows) -> SevenBySevenJournalDraftReview:
        if not bool(row["draft_review_ready"]):
            raise SevenBySevenJournalDraftValidation(
                "The protected 7x7 source event is blocked for draft review."
            )
        if bool(row["posting_enabled"]) or bool(row["automatic_source_posting"]):
            raise SevenBySevenJournalDraftValidation(
                "Protected 7x7 draft review unexpectedly enables posting or automatic source posting."
            )
        coordinates = tuple(
            SevenBySevenJournalCoordinate(
                line_number=int(item["line_number"]),
                journal_component=str(item["journal_component"]),
                account_id=UUID(str(item["account_id"])),
                account_code=str(item["account_code"]),
                account_system_key=str(item["account_system_key"]),
                account_name=str(item["account_name"]),
                debit=_money(item["debit"]),
                credit=_money(item["credit"]),
            )
            for item in coordinate_rows
        )
        if len(coordinates) != int(row["coordinate_line_count"]):
            raise SevenBySevenJournalDraftConflict(
                "Protected 7x7 coordinate row count changed during review."
            )
        return SevenBySevenJournalDraftReview(
            transaction_id=UUID(str(row["transaction_id"])),
            loan_id=UUID(str(row["loan_id"])),
            loan_number=str(row["loan_number"]),
            client_id=UUID(str(row["client_id"])),
            client_code=str(row["client_code"]),
            client_name=str(row["client_name"]),
            posting_date=row["posting_date"],
            fiscal_period_id=UUID(str(row["fiscal_period_id"])),
            source_event_key=str(row["source_event_key"]),
            source_event_review_token=str(row["source_event_review_token"]),
            coordinate_digest=str(row["coordinate_digest"]),
            source_cash_amount=_money(row["source_cash_amount"]),
            eir_interest_accrual=_money(row["eir_interest_accrual"]),
            accounting_eir_interest_received=_money(row["accounting_eir_interest_received"]),
            accounting_7x7_principal_received=_money(row["accounting_7x7_principal_received"]),
            coordinate_line_count=int(row["coordinate_line_count"]),
            total_debit=_money(row["total_debit"]),
            total_credit=_money(row["total_credit"]),
            draft_policy_version=str(row["draft_policy_version"]),
            coordinates=coordinates,
            draft_review_ready=True,
        )

    @staticmethod
    def _status_from_row(row) -> SevenBySevenJournalDraftStatus:
        return SevenBySevenJournalDraftStatus(
            preparation_id=UUID(str(row["preparation_id"])),
            transaction_id=UUID(str(row["transaction_id"])),
            loan_id=UUID(str(row["loan_id"])),
            client_id=UUID(str(row["client_id"])),
            journal_entry_id=UUID(str(row["journal_entry_id"])),
            source_event_key=str(row["source_event_key"]),
            source_event_review_token=str(row["source_event_review_token"]),
            coordinate_digest=str(row["coordinate_digest"]),
            draft_policy_version=str(row["draft_policy_version"]),
            posting_date=row["posting_date"],
            fiscal_period_id=UUID(str(row["fiscal_period_id"])),
            fiscal_period_label=str(row["fiscal_period_label"]),
            fiscal_period_status=str(row["fiscal_period_status"]),
            source_cash_amount=_money(row["source_cash_amount"]),
            eir_interest_accrual=_money(row["eir_interest_accrual"]),
            accounting_eir_interest_received=_money(row["accounting_eir_interest_received"]),
            accounting_7x7_principal_received=_money(row["accounting_7x7_principal_received"]),
            coordinate_line_count=int(row["coordinate_line_count"]),
            prepared_total_debit=_money(row["prepared_total_debit"]),
            prepared_total_credit=_money(row["prepared_total_credit"]),
            prepared_by_user_id=UUID(str(row["prepared_by_user_id"])),
            prepared_at=row["prepared_at"],
            journal_status=str(row["journal_status"]),
            entry_number=None if row["entry_number"] is None else str(row["entry_number"]),
            line_count=int(row["line_count"]),
            total_debit=_money(row["total_debit"]),
            total_credit=_money(row["total_credit"]),
            draft_integrity_ready=bool(row["draft_integrity_ready"]),
            posting_enabled=bool(row["posting_enabled"]),
            automatic_source_posting_enabled=bool(row["automatic_source_posting"]),
        )

    @staticmethod
    def _map_error(error: psycopg.Error) -> SevenBySevenJournalDraftError:
        message = str(error).split("CONTEXT:", 1)[0].strip()
        lowered = message.lower()
        if "not found" in lowered:
            return SevenBySevenJournalDraftNotFound(message)
        if any(marker in lowered for marker in (
            "changed",
            "already exists",
            "existing protected",
            "integrity",
            "different reviewed",
            "refresh management review",
        )):
            return SevenBySevenJournalDraftConflict(message)
        return SevenBySevenJournalDraftValidation(message)
