from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .database import open_connection


class RemittanceTransferJournalError(RuntimeError):
    code = "remittance_transfer_journal_error"


class RemittanceTransferJournalNotFound(RemittanceTransferJournalError):
    code = "remittance_transfer_journal_not_found"


class RemittanceTransferJournalConflict(RemittanceTransferJournalError):
    code = "remittance_transfer_journal_conflict"


class RemittanceTransferJournalInvalid(RemittanceTransferJournalError):
    code = "remittance_transfer_journal_invalid"


@dataclass(frozen=True, slots=True)
class RemittanceTransferJournalStatusRecord:
    preparation_id: UUID
    remittance_id: UUID
    transfer_evidence_id: UUID
    journal_entry_id: UUID
    source_event_key: str
    draft_review_token: str
    posting_date: date
    fiscal_period_id: UUID
    debit_account_id: UUID
    debit_account_system_key: str
    credit_account_id: UUID
    credit_account_system_key: str
    amount: Decimal
    journal_status: str
    entry_number: str | None
    posting_id: UUID | None
    posting_review_token: str | None
    posted_by_user_id: UUID | None
    posted_at: datetime | None
    reversal_id: UUID | None
    reversal_journal_entry_id: UUID | None
    reversal_entry_number: str | None
    reversal_posting_date: date | None
    reversal_reason: str | None
    posting_ready: bool
    posted_audit_exact: bool
    reversal_audit_exact: bool
    lifecycle_status: str
    income_recognition: bool
    explicit_management_posting: bool
    automatic_source_posting: bool


class PostgresRemittanceTransferJournalRepository:
    def list_status(self, *, limit: int = 100) -> tuple[RemittanceTransferJournalStatusRecord, ...]:
        safe_limit = max(1, min(int(limit), 250))
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    rows = cursor.execute(
                        """
                        select *
                        from accounting.remittance_transfer_journal_status
                        order by posting_date desc, preparation_id desc
                        limit %s
                        """,
                        (safe_limit,),
                    ).fetchall()
            return tuple(self._status_from_row(row) for row in rows)
        except psycopg.Error as error:
            raise self._map_error(error) from error

    def get_status(self, *, preparation_id: UUID) -> RemittanceTransferJournalStatusRecord:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    row = cursor.execute(
                        """
                        select *
                        from accounting.remittance_transfer_journal_status
                        where preparation_id = %s
                        """,
                        (preparation_id,),
                    ).fetchone()
            if row is None:
                raise RemittanceTransferJournalNotFound(
                    "Protected remittance-transfer journal preparation was not found."
                )
            return self._status_from_row(row)
        except psycopg.Error as error:
            raise self._map_error(error) from error

    def prepare(
        self,
        *,
        actor_user_id: UUID,
        remittance_id: UUID,
        review_token: str,
        transfer_evidence_id: UUID,
        source_event_key: str,
        posting_date: date,
        debit_account_system_key: str,
        credit_account_system_key: str,
        amount: Decimal,
        coordinate_policy_version: str,
        draft_policy_version: str,
    ) -> RemittanceTransferJournalStatusRecord:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    preparation_id = cursor.execute(
                        """
                        select accounting.create_remittance_transfer_journal_draft(
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        ) as preparation_id
                        """,
                        (
                            remittance_id,
                            actor_user_id,
                            review_token,
                            transfer_evidence_id,
                            source_event_key,
                            posting_date,
                            debit_account_system_key,
                            credit_account_system_key,
                            amount,
                            coordinate_policy_version,
                            draft_policy_version,
                        ),
                    ).fetchone()["preparation_id"]
                    row = cursor.execute(
                        "select * from accounting.remittance_transfer_journal_status where preparation_id = %s",
                        (preparation_id,),
                    ).fetchone()
                    if row is None:
                        raise RemittanceTransferJournalNotFound(
                            "Protected remittance-transfer journal preparation was not found after creation."
                        )
                    return self._status_from_row(row)
        except psycopg.Error as error:
            raise self._map_error(error) from error

    def post(
        self,
        *,
        actor_user_id: UUID,
        preparation_id: UUID,
        posting_review_token: str,
        expected_journal_entry_id: UUID,
        expected_source_event_key: str,
        expected_draft_review_token: str,
        expected_amount: Decimal,
        posting_policy_version: str,
    ) -> RemittanceTransferJournalStatusRecord:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        select accounting.post_remittance_transfer_journal(
                            %s, %s, %s, %s, %s, %s, %s, %s
                        )
                        """,
                        (
                            preparation_id,
                            actor_user_id,
                            posting_review_token,
                            expected_journal_entry_id,
                            expected_source_event_key,
                            expected_draft_review_token,
                            expected_amount,
                            posting_policy_version,
                        ),
                    )
                    row = cursor.execute(
                        "select * from accounting.remittance_transfer_journal_status where preparation_id = %s",
                        (preparation_id,),
                    ).fetchone()
                    if row is None:
                        raise RemittanceTransferJournalNotFound(
                            "Protected remittance-transfer journal preparation was not found after posting."
                        )
                    return self._status_from_row(row)
        except psycopg.Error as error:
            raise self._map_error(error) from error

    def reverse(
        self,
        *,
        actor_user_id: UUID,
        posting_id: UUID,
        reversal_posting_date: date,
        reason: str,
    ) -> RemittanceTransferJournalStatusRecord:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        "select accounting.reverse_posted_remittance_transfer(%s, %s, %s, %s)",
                        (posting_id, actor_user_id, reversal_posting_date, reason),
                    )
                    row = cursor.execute(
                        """
                        select status.*
                        from accounting.remittance_transfer_journal_status status
                        where status.posting_id = %s
                        """,
                        (posting_id,),
                    ).fetchone()
                    if row is None:
                        raise RemittanceTransferJournalNotFound(
                            "Protected remittance-transfer posting was not found after reversal."
                        )
                    return self._status_from_row(row)
        except psycopg.Error as error:
            raise self._map_error(error) from error

    @staticmethod
    def _status_from_row(row) -> RemittanceTransferJournalStatusRecord:
        return RemittanceTransferJournalStatusRecord(
            preparation_id=row["preparation_id"],
            remittance_id=row["remittance_id"],
            transfer_evidence_id=row["transfer_evidence_id"],
            journal_entry_id=row["journal_entry_id"],
            source_event_key=str(row["source_event_key"]),
            draft_review_token=str(row["draft_review_token"]),
            posting_date=row["posting_date"],
            fiscal_period_id=row["fiscal_period_id"],
            debit_account_id=row["debit_account_id"],
            debit_account_system_key=str(row["debit_account_system_key"]),
            credit_account_id=row["credit_account_id"],
            credit_account_system_key=str(row["credit_account_system_key"]),
            amount=Decimal(row["amount"]),
            journal_status=str(row["journal_status"]),
            entry_number=str(row["entry_number"]) if row["entry_number"] else None,
            posting_id=row["posting_id"],
            posting_review_token=(
                str(row["posting_review_token"])
                if row["posting_review_token"]
                else None
            ),
            posted_by_user_id=row["posted_by_user_id"],
            posted_at=row["posted_at"],
            reversal_id=row["reversal_id"],
            reversal_journal_entry_id=row["reversal_journal_entry_id"],
            reversal_entry_number=(
                str(row["reversal_entry_number"])
                if row["reversal_entry_number"]
                else None
            ),
            reversal_posting_date=row["reversal_posting_date"],
            reversal_reason=(
                str(row["reversal_reason"]) if row["reversal_reason"] else None
            ),
            posting_ready=bool(row["posting_ready"]),
            posted_audit_exact=bool(row["posted_audit_exact"]),
            reversal_audit_exact=bool(row["reversal_audit_exact"]),
            lifecycle_status=str(row["lifecycle_status"]),
            income_recognition=bool(row["income_recognition"]),
            explicit_management_posting=bool(row["explicit_management_posting"]),
            automatic_source_posting=bool(row["automatic_source_posting"]),
        )

    @staticmethod
    def _map_error(error: psycopg.Error) -> RemittanceTransferJournalError:
        message = str(error).split("CONTEXT:", 1)[0].strip()
        lower = message.lower()
        if "not found" in lower:
            return RemittanceTransferJournalNotFound(message)
        if (
            "already" in lower
            or "existing" in lower
            or "changed" in lower
            or "immutable" in lower
            or "only be reversed" in lower
            or "cannot" in lower
        ):
            return RemittanceTransferJournalConflict(message)
        return RemittanceTransferJournalInvalid(
            message or "Protected remittance-transfer journal validation failed."
        )