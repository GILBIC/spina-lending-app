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
    preparation_ready: bool
    preparation_blocker: str | None
    opening_balance_posting_enabled: bool
    automatic_source_posting_enabled: bool
    posting_ready: bool
    posting_blocker: str | None
    posted_by_user_id: UUID | None
    posted_at: datetime | None


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

    def post(
        self,
        *,
        actor_user_id: UUID,
        workbook_id: UUID,
    ) -> OpeningBalanceJournalPreparation:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        "select accounting.post_opening_balance_journal(%s, %s) as entry_number",
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
                prep.workbook_id,
                prep.cutover_date,
                prep.workbook_status,
                prep.journal_entry_id,
                prep.journal_status,
                prep.entry_number,
                prep.journal_created_at,
                prep.prepared_by_user_id,
                prep.prepared_at,
                prep.journal_line_count,
                prep.total_debit,
                prep.total_credit,
                prep.draft_prepared,
                prep.preparation_ready,
                prep.preparation_blocker,
                coalesce(posting.opening_balance_posting_enabled, false)
                    as opening_balance_posting_enabled,
                coalesce(posting.automatic_source_posting_enabled, false)
                    as automatic_source_posting_enabled,
                coalesce(posting.posting_ready, false) as posting_ready,
                posting.posting_blocker,
                posting.posted_by_user_id,
                posting.posted_at
            from accounting.opening_balance_journal_preparation_status prep
            left join accounting.opening_balance_journal_posting_status posting
              on posting.workbook_id = prep.workbook_id
            where prep.workbook_id = %s
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
            preparation_ready=bool(row["preparation_ready"]),
            preparation_blocker=(
                str(row["preparation_blocker"])
                if row["preparation_blocker"]
                else None
            ),
            opening_balance_posting_enabled=bool(
                row["opening_balance_posting_enabled"]
            ),
            automatic_source_posting_enabled=bool(
                row["automatic_source_posting_enabled"]
            ),
            posting_ready=bool(row["posting_ready"]),
            posting_blocker=(
                str(row["posting_blocker"]) if row["posting_blocker"] else None
            ),
            posted_by_user_id=(
                UUID(str(row["posted_by_user_id"]))
                if row["posted_by_user_id"] is not None
                else None
            ),
            posted_at=row["posted_at"],
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
            or "identity is invalid" in lowered
            or "without the protected posting audit" in lowered
            or "posting audit exists" in lowered
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
            or "no longer matches" in lowered
            or "period is open" in lowered
            or "period must remain open" in lowered
        ):
            return OpeningBalanceJournalValidation(message)
        return OpeningBalanceJournalError(message)
