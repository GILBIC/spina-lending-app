from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from psycopg.rows import dict_row

from .database import open_connection
from .source_event_accounting_preview import (
    CollectionAccountingPreview,
    CollectionSourceEvent,
    build_collection_accounting_preview,
)


REQUIRED_ACCOUNT_KEYS = (
    "cash_collector_custody",
    "loans_receivable_regular",
    "loans_receivable_7x7",
    "accrued_interest_receivable",
)


@dataclass(frozen=True, slots=True)
class SourceEventCursor:
    collection_date: date
    accepted_at: datetime
    transaction_id: UUID


@dataclass(frozen=True, slots=True)
class SourceEventAccountingPreviewPack:
    cutover_date: date | None
    workbook_status: str | None
    opening_balance_posted: bool
    opening_balance_entry_number: str | None
    account_configuration_ready: bool
    account_configuration_blocker: str | None
    automatic_source_posting_enabled: bool
    eir_income_included_in_collection_mapping: bool
    has_more: bool
    next_cursor: str | None
    events: tuple[CollectionAccountingPreview, ...]


def encode_source_event_cursor(event: CollectionSourceEvent) -> str:
    raw = json.dumps(
        {
            "collection_date": event.collection_date.isoformat(),
            "accepted_at": event.accepted_at.isoformat(),
            "transaction_id": str(event.transaction_id),
        },
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_source_event_cursor(value: str) -> SourceEventCursor:
    text = value.strip()
    if not text:
        raise ValueError("Source-event cursor cannot be blank.")
    try:
        padded = text + "=" * (-len(text) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError
        return SourceEventCursor(
            collection_date=date.fromisoformat(str(payload["collection_date"])),
            accepted_at=datetime.fromisoformat(str(payload["accepted_at"])),
            transaction_id=UUID(str(payload["transaction_id"])),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError("Source-event cursor is invalid.") from error


class PostgresSourceEventAccountingRepository:
    def load_collection_preview(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 100,
        cursor: str | None = None,
    ) -> SourceEventAccountingPreviewPack:
        safe_limit = max(1, min(int(limit), 250))
        decoded_cursor = decode_source_event_cursor(cursor) if cursor is not None else None
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as db_cursor:
                cutover = self._load_cutover(db_cursor)
                account_ready, account_blocker = self._account_configuration(db_cursor)
                loaded = self._load_collection_events(
                    db_cursor,
                    start_date=start_date,
                    end_date=end_date,
                    cursor=decoded_cursor,
                    limit=safe_limit + 1,
                )

        has_more = len(loaded) > safe_limit
        events = loaded[:safe_limit]
        next_cursor = (
            encode_source_event_cursor(events[-1]) if has_more and events else None
        )
        previews = tuple(
            build_collection_accounting_preview(
                event,
                cutover_date=cutover["cutover_date"] if cutover else None,
            )
            for event in events
        )
        return SourceEventAccountingPreviewPack(
            cutover_date=cutover["cutover_date"] if cutover else None,
            workbook_status=str(cutover["workbook_status"]) if cutover else None,
            opening_balance_posted=bool(cutover and cutover["opening_balance_posted"]),
            opening_balance_entry_number=(
                str(cutover["opening_balance_entry_number"])
                if cutover and cutover["opening_balance_entry_number"]
                else None
            ),
            account_configuration_ready=account_ready,
            account_configuration_blocker=account_blocker,
            automatic_source_posting_enabled=False,
            eir_income_included_in_collection_mapping=False,
            has_more=has_more,
            next_cursor=next_cursor,
            events=previews,
        )

    @staticmethod
    def _load_cutover(cursor):
        cursor.execute(
            """
            select
                workbook.cutover_date,
                workbook.status as workbook_status,
                (posting.workbook_id is not null) as opening_balance_posted,
                posting.entry_number as opening_balance_entry_number
            from accounting.opening_balance_workbooks workbook
            left join accounting.opening_balance_journal_postings posting
              on posting.workbook_id = workbook.id
            order by workbook.created_at desc
            limit 1
            """
        )
        return cursor.fetchone()

    @staticmethod
    def _account_configuration(cursor) -> tuple[bool, str | None]:
        cursor.execute(
            """
            select system_key, is_active, is_posting
            from accounting.accounts
            where system_key = any(%s)
            """,
            (list(REQUIRED_ACCOUNT_KEYS),),
        )
        rows = {str(row["system_key"]): row for row in cursor.fetchall()}
        missing = [key for key in REQUIRED_ACCOUNT_KEYS if key not in rows]
        invalid = [
            key
            for key, row in rows.items()
            if not bool(row["is_active"]) or not bool(row["is_posting"])
        ]
        if missing:
            return False, "Missing required accounting account mapping: " + ", ".join(missing)
        if invalid:
            return False, "Required accounting accounts are inactive or non-posting: " + ", ".join(invalid)
        return True, None

    @staticmethod
    def _load_collection_events(
        cursor,
        *,
        start_date: date | None,
        end_date: date | None,
        cursor: SourceEventCursor | None,
        limit: int,
    ) -> tuple[CollectionSourceEvent, ...]:
        cursor.execute(
            """
            select
                transaction.id as transaction_id,
                transaction.receipt_number,
                transaction.client_id,
                client.client_code,
                client.full_name as client_name,
                transaction.loan_id,
                loan.loan_number,
                loan_type.code as loan_type_code,
                loan_type.name as loan_type_name,
                loan_type.calculation_mode,
                transaction.collection_date,
                transaction.accepted_at,
                transaction.entry_type,
                transaction.amount,
                transaction.is_voided,
                transaction.voided_at,
                journal.id as journal_entry_id,
                journal.status as journal_status,
                journal.entry_number as journal_entry_number,
                reversal.id as reversal_entry_id,
                reversal.status as reversal_status,
                reversal.entry_number as reversal_entry_number
            from lending.collection_transactions transaction
            join lending.clients client on client.id = transaction.client_id
            join lending.loans loan on loan.id = transaction.loan_id
            join lending.loan_types loan_type on loan_type.id = loan.loan_type_id
            left join accounting.journal_entries journal
              on journal.source_event_key = 'collection:' || transaction.id::text
            left join accounting.journal_entries reversal
              on reversal.reversal_of_entry_id = journal.id
            where (%s::date is null or transaction.collection_date >= %s::date)
              and (%s::date is null or transaction.collection_date <= %s::date)
              and (
                    %s::date is null
                    or (
                        transaction.collection_date,
                        transaction.accepted_at,
                        transaction.id
                    ) < (%s::date, %s::timestamptz, %s::uuid)
              )
            order by transaction.collection_date desc, transaction.accepted_at desc, transaction.id desc
            limit %s
            """,
            (
                start_date,
                start_date,
                end_date,
                end_date,
                cursor.collection_date if cursor else None,
                cursor.collection_date if cursor else None,
                cursor.accepted_at if cursor else None,
                cursor.transaction_id if cursor else None,
                limit,
            ),
        )
        return tuple(
            CollectionSourceEvent(
                transaction_id=UUID(str(row["transaction_id"])),
                receipt_number=str(row["receipt_number"]),
                client_id=UUID(str(row["client_id"])),
                client_code=str(row["client_code"]),
                client_name=str(row["client_name"]),
                loan_id=UUID(str(row["loan_id"])),
                loan_number=str(row["loan_number"]),
                loan_type_code=str(row["loan_type_code"]),
                loan_type_name=str(row["loan_type_name"]),
                calculation_mode=str(row["calculation_mode"]),
                collection_date=row["collection_date"],
                accepted_at=row["accepted_at"],
                entry_type=str(row["entry_type"]),
                amount=Decimal(row["amount"] or 0),
                is_voided=bool(row["is_voided"]),
                voided_at=row["voided_at"],
                journal_entry_id=(
                    UUID(str(row["journal_entry_id"]))
                    if row["journal_entry_id"] is not None
                    else None
                ),
                journal_status=(
                    str(row["journal_status"]) if row["journal_status"] else None
                ),
                journal_entry_number=(
                    str(row["journal_entry_number"])
                    if row["journal_entry_number"]
                    else None
                ),
                reversal_entry_id=(
                    UUID(str(row["reversal_entry_id"]))
                    if row["reversal_entry_id"] is not None
                    else None
                ),
                reversal_status=(
                    str(row["reversal_status"]) if row["reversal_status"] else None
                ),
                reversal_entry_number=(
                    str(row["reversal_entry_number"])
                    if row["reversal_entry_number"]
                    else None
                ),
            )
            for row in cursor.fetchall()
        )
