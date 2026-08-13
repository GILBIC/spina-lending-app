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


POSTING_POLICY_VERSION = "seven_by_seven_source_event_journal_posting_v1"


@dataclass(frozen=True, slots=True)
class SevenBySevenJournalPostingStatus:
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
    posting_id: UUID | None
    posting_review_token: str
    posting_policy_version: str
    posted_by_user_id: UUID | None
    posted_at: datetime | None
    posting_ready: bool
    posted_audit_exact: bool
    protected_posting_enabled: bool
    reversal_enabled: bool
    automatic_source_posting_enabled: bool

    @property
    def posted(self) -> bool:
        return self.posting_id is not None and self.posted_audit_exact


class SevenBySevenJournalPostingError(RuntimeError):
    code = "seven_by_seven_journal_posting_error"


class SevenBySevenJournalPostingNotFound(SevenBySevenJournalPostingError):
    code = "seven_by_seven_journal_posting_not_found"


class SevenBySevenJournalPostingConflict(SevenBySevenJournalPostingError):
    code = "seven_by_seven_journal_posting_conflict"


class SevenBySevenJournalPostingValidation(SevenBySevenJournalPostingError):
    code = "seven_by_seven_journal_posting_validation"


def _money(value: object) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _posting_review_token(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class PostgresSevenBySevenJournalPostingRepository:
    def load_status(self, *, transaction_id: UUID) -> SevenBySevenJournalPostingStatus:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    row = cursor.execute(
                        """
                        select *
                        from accounting.seven_by_seven_journal_posting_status
                        where transaction_id = %s
                        """,
                        (transaction_id,),
                    ).fetchone()
                    if row is None:
                        raise SevenBySevenJournalPostingNotFound(
                            "Protected 7x7 journal draft was not found."
                        )
                    return self._status_from_row(row)
        except SevenBySevenJournalPostingError:
            raise
        except psycopg.Error as error:
            raise self._map_error(error) from error

    def post(
        self,
        *,
        actor_user_id: UUID,
        transaction_id: UUID,
        expected_posting_review_token: str,
    ) -> SevenBySevenJournalPostingStatus:
        normalized_token = expected_posting_review_token.strip().lower()
        if not self._valid_token(normalized_token):
            raise SevenBySevenJournalPostingValidation(
                "The protected 7x7 posting review token is invalid."
            )

        current = self.load_status(transaction_id=transaction_id)
        if current.posting_review_token != normalized_token:
            raise SevenBySevenJournalPostingConflict(
                "Protected 7x7 posting facts changed. Refresh Management review before posting."
            )
        if not current.posting_ready and not current.posted:
            raise SevenBySevenJournalPostingConflict(
                "Protected 7x7 journal is not ready for posting."
            )

        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    row = cursor.execute(
                        """
                        select accounting.post_seven_by_seven_journal(
                            %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s, %s
                        ) as posting_id
                        """,
                        (
                            current.preparation_id,
                            actor_user_id,
                            normalized_token,
                            current.journal_entry_id,
                            current.source_event_key,
                            current.source_event_review_token,
                            current.coordinate_digest,
                            current.posting_date,
                            current.fiscal_period_id,
                            current.source_cash_amount,
                            current.eir_interest_accrual,
                            current.accounting_eir_interest_received,
                            current.accounting_7x7_principal_received,
                            current.coordinate_line_count,
                            current.prepared_total_debit,
                            current.prepared_total_credit,
                            POSTING_POLICY_VERSION,
                        ),
                    ).fetchone()
                    if row is None or row["posting_id"] is None:
                        raise SevenBySevenJournalPostingConflict(
                            "Protected 7x7 posting returned no immutable posting audit."
                        )
        except SevenBySevenJournalPostingError:
            raise
        except psycopg.Error as error:
            raise self._map_error(error) from error

        posted = self.load_status(transaction_id=transaction_id)
        if not posted.posted:
            raise SevenBySevenJournalPostingConflict(
                "Protected 7x7 posting failed immutable post-write audit review."
            )
        if posted.posting_review_token != normalized_token:
            raise SevenBySevenJournalPostingConflict(
                "Protected 7x7 posting review identity changed during posting."
            )
        if posted.reversal_enabled or posted.automatic_source_posting_enabled:
            raise SevenBySevenJournalPostingConflict(
                "Protected 7x7 posting unexpectedly enabled reversal or automatic source posting."
            )
        return posted

    @staticmethod
    def _status_from_row(row) -> SevenBySevenJournalPostingStatus:
        source_cash_amount = _money(row["source_cash_amount"])
        eir_interest_accrual = _money(row["eir_interest_accrual"])
        accounting_eir_interest_received = _money(row["accounting_eir_interest_received"])
        accounting_7x7_principal_received = _money(row["accounting_7x7_principal_received"])
        prepared_total_debit = _money(row["prepared_total_debit"])
        prepared_total_credit = _money(row["prepared_total_credit"])
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
            "transaction_id": str(row["transaction_id"]),
            "loan_id": str(row["loan_id"]),
            "client_id": str(row["client_id"]),
            "journal_entry_id": str(row["journal_entry_id"]),
            "source_event_key": str(row["source_event_key"]),
            "source_event_review_token": str(row["source_event_review_token"]),
            "coordinate_digest": str(row["coordinate_digest"]),
            "draft_policy_version": str(row["draft_policy_version"]),
            "posting_date": row["posting_date"].isoformat(),
            "fiscal_period_id": str(row["fiscal_period_id"]),
            "source_cash_amount": format(source_cash_amount, ".2f"),
            "eir_interest_accrual": format(eir_interest_accrual, ".2f"),
            "accounting_eir_interest_received": format(
                accounting_eir_interest_received, ".2f"
            ),
            "accounting_7x7_principal_received": format(
                accounting_7x7_principal_received, ".2f"
            ),
            "coordinate_line_count": int(row["coordinate_line_count"]),
            "total_debit": format(prepared_total_debit, ".2f"),
            "total_credit": format(prepared_total_credit, ".2f"),
        }
        computed_posting_token = _posting_review_token(token_payload)
        if stored_posting_token is not None and stored_posting_token != computed_posting_token:
            raise SevenBySevenJournalPostingConflict(
                "Immutable protected 7x7 posting audit token no longer matches the posted facts."
            )

        return SevenBySevenJournalPostingStatus(
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
            source_cash_amount=source_cash_amount,
            eir_interest_accrual=eir_interest_accrual,
            accounting_eir_interest_received=accounting_eir_interest_received,
            accounting_7x7_principal_received=accounting_7x7_principal_received,
            coordinate_line_count=int(row["coordinate_line_count"]),
            prepared_total_debit=prepared_total_debit,
            prepared_total_credit=prepared_total_credit,
            prepared_by_user_id=UUID(str(row["prepared_by_user_id"])),
            prepared_at=row["prepared_at"],
            journal_status=str(row["journal_status"]),
            entry_number=None if row["entry_number"] is None else str(row["entry_number"]),
            line_count=int(row["line_count"]),
            total_debit=total_debit,
            total_credit=total_credit,
            posting_id=(
                None if row["posting_id"] is None else UUID(str(row["posting_id"]))
            ),
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
            reversal_enabled=bool(row["reversal_enabled"]),
            automatic_source_posting_enabled=bool(row["automatic_source_posting"]),
        )

    @staticmethod
    def _valid_token(value: str) -> bool:
        return len(value) == 64 and all(
            character in "0123456789abcdef" for character in value
        )

    @staticmethod
    def _map_error(error: psycopg.Error) -> SevenBySevenJournalPostingError:
        message = str(error).split("CONTEXT:", 1)[0].strip()
        lowered = message.lower()
        if "was not found" in lowered:
            return SevenBySevenJournalPostingNotFound(message)
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
                "stale",
                "refresh management review",
                "unique",
            )
        ):
            return SevenBySevenJournalPostingConflict(message)
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
                "coordinate",
            )
        ):
            return SevenBySevenJournalPostingValidation(message)
        return SevenBySevenJournalPostingError(message)
