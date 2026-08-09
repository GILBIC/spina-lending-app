from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .database import open_connection


@dataclass(frozen=True, slots=True)
class OpeningBalanceJournalPreparation:
    workbook_id: UUID
    cutover_date: date
    workbook_status: str
    journal_entry_id: UUID | None
    journal_status: str | None
    entry_number: str | None
    journal_created_at: datetime | None
    prepared_by_user_id: UUID | None
    prepared_at: datetime | None
    journal_line_count: int
    total_debit: Decimal
    total_credit: Decimal
    draft_prepared: bool
    opening_balance_posting_enabled: bool
    automatic_source_posting_enabled: bool


class OpeningBalanceJournalError(RuntimeError):
    code = "opening_balance_journal_error"


class OpeningBalanceJournalNotFound(OpeningBalanceJournalError):
    code = "opening_balance_journal_not_found"


class OpeningBalanceJournalConflict(OpeningBalanceJournalError):
    code = "opening_balance_journal_conflict"


class OpeningBalanceJournalValidation(OpeningBalanceJournalError):
    code = "opening_balance_journal_validation"


class PostgresOpeningBalanceJournalRepository:
    def load_status(self, *, workbook_id: UUID) -> OpeningBalanceJournalPreparation:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                return self._load_status(cursor, workbook_id)

    def prepare_draft(
        self,
        *,
        actor_user_id: UUID,
        workbook_id: UUID,
    ) -> OpeningBalanceJournalPreparation:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        "select accounting.create_opening_balance_journal_draft(%s, %s)",
                        (workbook_id, actor_user_id),
                    )
                    cursor.fetchone()
                    return self._load_status(cursor, workbook_id)
        except psycopg.Error as error:
            raise self._map_error(error) from error

    @staticmethod
    def _load_status(cursor, workbook_id: UUID) -> OpeningBalanceJournalPreparation:
        cursor.execute(
            """
            select
                workbook_id,
                cutover_date,
                workbook_status,
                journal_entry_id,
                journal_status,
                entry_number,
                journal_created_at,
                prepared_by_user_id,
                prepared_at,
                journal_line_count,
                total_debit,
                total_credit,
                draft_prepared,
                opening_balance_posting_enabled,
                automatic_source_posting_enabled
            from accounting.opening_balance_journal_preparation_status
            where workbook_id = %s
            """,
            (workbook_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise OpeningBalanceJournalNotFound("Opening-balance workbook was not found.")
        return OpeningBalanceJournalPreparation(
            workbook_id=UUID(str(row["workbook_id"])),
            cutover_date=row["cutover_date"],
            workbook_status=str(row["workbook_status"]),
            journal_entry_id=(
                UUID(str(row["journal_entry_id"]))
                if row["journal_entry_id"] is not None
                else None
            ),
            journal_status=(
                str(row["journal_status"]) if row["journal_status"] else None
            ),
            entry_number=(str(row["entry_number"]) if row["entry_number"] else None),
            journal_created_at=row["journal_created_at"],
            prepared_by_user_id=(
                UUID(str(row["prepared_by_user_id"]))
                if row["prepared_by_user_id"] is not None
                else None
            ),
            prepared_at=row["prepared_at"],
            journal_line_count=int(row["journal_line_count"] or 0),
            total_debit=Decimal(row["total_debit"] or 0),
            total_credit=Decimal(row["total_credit"] or 0),
            draft_prepared=bool(row["draft_prepared"]),
            opening_balance_posting_enabled=bool(
                row["opening_balance_posting_enabled"]
            ),
            automatic_source_posting_enabled=bool(
                row["automatic_source_posting_enabled"]
            ),
        )

    @staticmethod
    def _map_error(error: psycopg.Error) -> OpeningBalanceJournalError:
        message = str(error).split("CONTEXT:", 1)[0].strip()
        lowered = message.lower()
        if "was not found" in lowered:
            return OpeningBalanceJournalNotFound(message)
        if (
            "review-ready" in lowered
            or "review ready" in lowered
            or "cannot be reopened" in lowered
            or "requires the protected" in lowered
        ):
            return OpeningBalanceJournalConflict(message)
        if (
            "requires" in lowered
            or "must" in lowered
            or "blocked" in lowered
            or "inactive" in lowered
            or "non-posting" in lowered
            or "verified" in lowered
            or "evidence" in lowered
            or "balanced" in lowered
        ):
            return OpeningBalanceJournalValidation(message)
        return OpeningBalanceJournalError(message)
