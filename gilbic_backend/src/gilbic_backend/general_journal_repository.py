from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .database import open_connection


@dataclass(frozen=True, slots=True)
class JournalLine:
    line_number: int
    account_code: str
    account_name: str
    description: str
    debit: Decimal
    credit: Decimal


@dataclass(frozen=True, slots=True)
class JournalEntry:
    entry_id: UUID
    entry_number: str | None
    period_id: UUID
    period_label: str
    posting_date: date
    description: str
    status: str
    source_type: str | None
    source_reference: str | None
    reversal_of_entry_id: UUID | None
    created_by_name: str
    posted_by_name: str | None
    created_at: datetime
    posted_at: datetime | None
    total_debit: Decimal
    total_credit: Decimal
    lines: tuple[JournalLine, ...]


@dataclass(frozen=True, slots=True)
class TrialBalanceLine:
    account_code: str
    account_name: str
    account_type: str
    normal_balance: str
    total_debit: Decimal
    total_credit: Decimal
    debit_balance: Decimal
    credit_balance: Decimal


@dataclass(frozen=True, slots=True)
class TrialBalance:
    period_id: UUID | None
    period_label: str | None
    total_debits: Decimal
    total_credits: Decimal
    balanced: bool
    lines: tuple[TrialBalanceLine, ...]


class GeneralJournalError(RuntimeError):
    code = "general_journal_error"


class JournalNotFound(GeneralJournalError):
    code = "journal_not_found"


class JournalConflict(GeneralJournalError):
    code = "journal_conflict"


class JournalValidationError(GeneralJournalError):
    code = "journal_validation_error"


class PostgresGeneralJournalRepository:
    def list_journals(self, *, limit: int = 100) -> tuple[JournalEntry, ...]:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select
                        journal.id,
                        journal.entry_number,
                        journal.fiscal_period_id,
                        period.label as period_label,
                        journal.posting_date,
                        journal.description,
                        journal.status,
                        journal.source_type,
                        journal.source_reference,
                        journal.reversal_of_entry_id,
                        created_by.full_name as created_by_name,
                        posted_by.full_name as posted_by_name,
                        journal.created_at,
                        journal.posted_at,
                        coalesce(sum(line.debit), 0) as total_debit,
                        coalesce(sum(line.credit), 0) as total_credit
                    from accounting.journal_entries journal
                    join accounting.fiscal_periods period
                      on period.id = journal.fiscal_period_id
                    join core.users created_by
                      on created_by.id = journal.created_by_user_id
                    left join core.users posted_by
                      on posted_by.id = journal.posted_by_user_id
                    left join accounting.journal_lines line
                      on line.journal_entry_id = journal.id
                    where not (
                        journal.source_type = 'opening_balance'
                        and journal.status = 'draft'
                    )
                    group by
                        journal.id,
                        period.label,
                        created_by.full_name,
                        posted_by.full_name
                    order by journal.posting_date desc, journal.created_at desc
                    limit %s
                    """,
                    (max(1, min(limit, 250)),),
                )
                rows = cursor.fetchall()
                entries: list[JournalEntry] = []
                for row in rows:
                    entries.append(self._entry_from_row(cursor, row))
                return tuple(entries)

    def get_journal(self, entry_id: UUID) -> JournalEntry:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select
                        journal.id,
                        journal.entry_number,
                        journal.fiscal_period_id,
                        period.label as period_label,
                        journal.posting_date,
                        journal.description,
                        journal.status,
                        journal.source_type,
                        journal.source_reference,
                        journal.reversal_of_entry_id,
                        created_by.full_name as created_by_name,
                        posted_by.full_name as posted_by_name,
                        journal.created_at,
                        journal.posted_at,
                        coalesce(sum(line.debit), 0) as total_debit,
                        coalesce(sum(line.credit), 0) as total_credit
                    from accounting.journal_entries journal
                    join accounting.fiscal_periods period
                      on period.id = journal.fiscal_period_id
                    join core.users created_by
                      on created_by.id = journal.created_by_user_id
                    left join core.users posted_by
                      on posted_by.id = journal.posted_by_user_id
                    left join accounting.journal_lines line
                      on line.journal_entry_id = journal.id
                    where journal.id = %s
                    group by
                        journal.id,
                        period.label,
                        created_by.full_name,
                        posted_by.full_name
                    """,
                    (entry_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise JournalNotFound("Journal entry was not found.")
                return self._entry_from_row(cursor, row)

    def create_manual_draft(
        self,
        *,
        actor_user_id: UUID,
        posting_date: date,
        description: str,
        lines: list[dict[str, object]],
    ) -> JournalEntry:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        select accounting.create_manual_journal_draft(
                            %s, %s, %s, %s::jsonb
                        ) as entry_id
                        """,
                        (posting_date, description, actor_user_id, psycopg.types.json.Jsonb(lines)),
                    )
                    entry_id = UUID(str(cursor.fetchone()["entry_id"]))
                    return self._get_journal_in_cursor(cursor, entry_id)
        except psycopg.Error as error:
            raise self._map_error(error) from error

    def update_manual_draft(
        self,
        *,
        entry_id: UUID,
        actor_user_id: UUID,
        posting_date: date,
        description: str,
        lines: list[dict[str, object]],
    ) -> JournalEntry:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        select accounting.update_manual_journal_draft(
                            %s, %s, %s, %s, %s::jsonb
                        )
                        """,
                        (
                            entry_id,
                            posting_date,
                            description,
                            actor_user_id,
                            psycopg.types.json.Jsonb(lines),
                        ),
                    )
                    return self._get_journal_in_cursor(cursor, entry_id)
        except psycopg.Error as error:
            raise self._map_error(error) from error

    def cancel_manual_draft(
        self,
        *,
        entry_id: UUID,
        actor_user_id: UUID,
    ) -> None:
        try:
            with open_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "select accounting.cancel_manual_journal_draft(%s, %s)",
                        (entry_id, actor_user_id),
                    )
        except psycopg.Error as error:
            raise self._map_error(error) from error

    def post_journal(
        self,
        *,
        entry_id: UUID,
        actor_user_id: UUID,
    ) -> JournalEntry:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        "select accounting.post_manual_journal_entry(%s, %s) as entry_number",
                        (entry_id, actor_user_id),
                    )
                    cursor.fetchone()
                    return self._get_journal_in_cursor(cursor, entry_id)
        except psycopg.Error as error:
            raise self._map_error(error) from error

    def create_reversal_draft(
        self,
        *,
        entry_id: UUID,
        actor_user_id: UUID,
        posting_date: date,
        description: str,
    ) -> JournalEntry:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        select accounting.create_manual_reversal_draft(
                            %s, %s, %s, %s
                        ) as reversal_id
                        """,
                        (entry_id, actor_user_id, posting_date, description),
                    )
                    reversal_id = UUID(str(cursor.fetchone()["reversal_id"]))
                    return self._get_journal_in_cursor(cursor, reversal_id)
        except psycopg.Error as error:
            raise self._map_error(error) from error

    def trial_balance(self, *, period_id: UUID | None = None) -> TrialBalance:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                period_label: str | None = None
                if period_id is not None:
                    cursor.execute(
                        "select label from accounting.fiscal_periods where id = %s",
                        (period_id,),
                    )
                    period_row = cursor.fetchone()
                    if period_row is None:
                        raise JournalNotFound("Accounting period was not found.")
                    period_label = str(period_row["label"])

                cursor.execute(
                    """
                    select
                        account.code,
                        account.name,
                        account.account_type,
                        account.normal_balance,
                        coalesce(sum(line.debit) filter (
                            where journal.status = 'posted'
                              and (%s::uuid is null or journal.fiscal_period_id = %s::uuid)
                        ), 0) as total_debit,
                        coalesce(sum(line.credit) filter (
                            where journal.status = 'posted'
                              and (%s::uuid is null or journal.fiscal_period_id = %s::uuid)
                        ), 0) as total_credit
                    from accounting.accounts account
                    left join accounting.journal_lines line
                      on line.account_id = account.id
                    left join accounting.journal_entries journal
                      on journal.id = line.journal_entry_id
                    group by account.id
                    order by account.code
                    """,
                    (period_id, period_id, period_id, period_id),
                )
                lines: list[TrialBalanceLine] = []
                total_debits = Decimal("0")
                total_credits = Decimal("0")
                for row in cursor.fetchall():
                    debit = Decimal(row["total_debit"] or 0)
                    credit = Decimal(row["total_credit"] or 0)
                    net = debit - credit
                    debit_balance = net if net > 0 else Decimal("0")
                    credit_balance = -net if net < 0 else Decimal("0")
                    total_debits += debit_balance
                    total_credits += credit_balance
                    lines.append(
                        TrialBalanceLine(
                            account_code=str(row["code"]),
                            account_name=str(row["name"]),
                            account_type=str(row["account_type"]),
                            normal_balance=str(row["normal_balance"]),
                            total_debit=debit,
                            total_credit=credit,
                            debit_balance=debit_balance,
                            credit_balance=credit_balance,
                        )
                    )
                return TrialBalance(
                    period_id=period_id,
                    period_label=period_label,
                    total_debits=total_debits,
                    total_credits=total_credits,
                    balanced=total_debits == total_credits,
                    lines=tuple(lines),
                )

    @classmethod
    def _get_journal_in_cursor(cls, cursor, entry_id: UUID) -> JournalEntry:
        cursor.execute(
            """
            select
                journal.id,
                journal.entry_number,
                journal.fiscal_period_id,
                period.label as period_label,
                journal.posting_date,
                journal.description,
                journal.status,
                journal.source_type,
                journal.source_reference,
                journal.reversal_of_entry_id,
                created_by.full_name as created_by_name,
                posted_by.full_name as posted_by_name,
                journal.created_at,
                journal.posted_at,
                coalesce(sum(line.debit), 0) as total_debit,
                coalesce(sum(line.credit), 0) as total_credit
            from accounting.journal_entries journal
            join accounting.fiscal_periods period
              on period.id = journal.fiscal_period_id
            join core.users created_by
              on created_by.id = journal.created_by_user_id
            left join core.users posted_by
              on posted_by.id = journal.posted_by_user_id
            left join accounting.journal_lines line
              on line.journal_entry_id = journal.id
            where journal.id = %s
            group by journal.id, period.label, created_by.full_name, posted_by.full_name
            """,
            (entry_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise JournalNotFound("Journal entry was not found.")
        return cls._entry_from_row(cursor, row)

    @staticmethod
    def _entry_from_row(cursor, row) -> JournalEntry:
        entry_id = UUID(str(row["id"]))
        cursor.execute(
            """
            select
                line.line_number,
                account.code as account_code,
                account.name as account_name,
                line.description,
                line.debit,
                line.credit
            from accounting.journal_lines line
            join accounting.accounts account on account.id = line.account_id
            where line.journal_entry_id = %s
            order by line.line_number
            """,
            (entry_id,),
        )
        lines = tuple(
            JournalLine(
                line_number=int(line["line_number"]),
                account_code=str(line["account_code"]),
                account_name=str(line["account_name"]),
                description=str(line["description"] or ""),
                debit=Decimal(line["debit"] or 0),
                credit=Decimal(line["credit"] or 0),
            )
            for line in cursor.fetchall()
        )
        return JournalEntry(
            entry_id=entry_id,
            entry_number=str(row["entry_number"]) if row["entry_number"] else None,
            period_id=UUID(str(row["fiscal_period_id"])),
            period_label=str(row["period_label"]),
            posting_date=row["posting_date"],
            description=str(row["description"]),
            status=str(row["status"]),
            source_type=str(row["source_type"]) if row["source_type"] else None,
            source_reference=(
                str(row["source_reference"]) if row["source_reference"] else None
            ),
            reversal_of_entry_id=(
                UUID(str(row["reversal_of_entry_id"]))
                if row["reversal_of_entry_id"]
                else None
            ),
            created_by_name=str(row["created_by_name"]),
            posted_by_name=(str(row["posted_by_name"]) if row["posted_by_name"] else None),
            created_at=row["created_at"],
            posted_at=row["posted_at"],
            total_debit=Decimal(row["total_debit"] or 0),
            total_credit=Decimal(row["total_credit"] or 0),
            lines=lines,
        )

    @staticmethod
    def _map_error(error: psycopg.Error) -> GeneralJournalError:
        message = str(error).split("CONTEXT:", 1)[0].strip()
        lowered = message.lower()
        if "was not found" in lowered:
            return JournalNotFound(message)
        if (
            "only a draft" in lowered
            or "only a manual draft" in lowered
            or "already has a reversal" in lowered
            or "can only be posted to an open" in lowered
            or "no open accounting period" in lowered
            or "protected opening-balance posting workflow" in lowered
        ):
            return JournalConflict(message)
        if (
            "requires at least two lines" in lowered
            or "must be balanced" in lowered
            or "not balanced" in lowered
            or "unknown, inactive" in lowered
            or "requires one active account" in lowered
            or "description is required" in lowered
            or "posting date is outside" in lowered
        ):
            return JournalValidationError(message)
        return GeneralJournalError(message or "General Journal operation failed.")
