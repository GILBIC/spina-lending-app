from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .database import open_connection
from .regular_journal_draft_repository import (
    PostgresRegularJournalDraftRepository,
    RegularJournalDraftReviewSetStatus,
)


@dataclass(frozen=True, slots=True)
class RegularJournalPostingStatus:
    loan_id: UUID
    review_set_fingerprint: str
    expected_transaction_count: int
    preparation_count: int
    expected_entry_count: int
    actual_entry_count: int
    draft_entry_count: int
    posted_entry_count: int
    total_debit: Decimal
    total_credit: Decimal
    posting_ready: bool
    posting_blocker: str | None
    posting_set_id: UUID | None
    audit_entry_count: int
    posted_by_user_id: UUID | None
    posted_at: datetime | None
    entry_numbers: tuple[str, ...]
    regular_journal_posting_enabled: bool = True
    automatic_source_posting_enabled: bool = False

    @property
    def posted(self) -> bool:
        return (
            self.posting_set_id is not None
            and self.expected_entry_count > 0
            and self.audit_entry_count == self.expected_entry_count
            and self.posted_entry_count == self.expected_entry_count
            and self.draft_entry_count == 0
        )


class RegularJournalPostingError(RuntimeError):
    code = "regular_journal_posting_error"


class RegularJournalPostingNotFound(RegularJournalPostingError):
    code = "regular_journal_posting_not_found"


class RegularJournalPostingConflict(RegularJournalPostingError):
    code = "regular_journal_posting_conflict"


class RegularJournalPostingValidation(RegularJournalPostingError):
    code = "regular_journal_posting_validation"


class PostgresRegularJournalPostingRepository:
    def __init__(
        self,
        *,
        draft_repository: PostgresRegularJournalDraftRepository | None = None,
    ) -> None:
        self._draft_repository = draft_repository or PostgresRegularJournalDraftRepository()

    def load_status(
        self,
        *,
        loan_id: UUID,
        review_set_fingerprint: str,
    ) -> RegularJournalPostingStatus:
        if not self._valid_fingerprint(review_set_fingerprint):
            raise RegularJournalPostingValidation(
                "The protected Regular journal review token is invalid."
            )

        review_set = self._find_review_set(
            loan_id=loan_id,
            review_set_fingerprint=review_set_fingerprint,
        )
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    audit = cursor.execute(
                        """
                        select
                            posting.id,
                            posting.expected_transaction_count,
                            posting.expected_entry_count,
                            posting.posted_by_user_id,
                            posting.posted_at,
                            count(posted_entry.journal_entry_id)::bigint as audit_entry_count
                        from accounting.regular_journal_posting_sets posting
                        left join accounting.regular_journal_posting_entries posted_entry
                          on posted_entry.posting_set_id = posting.id
                        where posting.loan_id = %s
                          and posting.review_set_fingerprint = %s
                        group by
                            posting.id,
                            posting.expected_transaction_count,
                            posting.expected_entry_count,
                            posting.posted_by_user_id,
                            posting.posted_at
                        """,
                        (loan_id, review_set_fingerprint),
                    ).fetchone()
                    entry_number_rows = ()
                    if audit is not None:
                        entry_number_rows = cursor.execute(
                            """
                            select posted_entry.entry_number
                            from accounting.regular_journal_posting_entries posted_entry
                            where posted_entry.posting_set_id = %s
                            order by posted_entry.transaction_id, posted_entry.sequence_order
                            """,
                            (audit["id"],),
                        ).fetchall()
        except psycopg.Error as error:
            raise self._map_error(error) from error

        expected_entry_count = sum(
            item.expected_entry_count for item in review_set.preparations
        )
        actual_entry_count = sum(
            item.actual_entry_count for item in review_set.preparations
        )
        draft_entry_count = sum(
            item.draft_entry_count for item in review_set.preparations
        )
        posted_entry_count = sum(
            item.posted_entry_count for item in review_set.preparations
        )
        total_debit = sum(
            (item.total_debit for item in review_set.preparations),
            Decimal("0.00"),
        )
        total_credit = sum(
            (item.total_credit for item in review_set.preparations),
            Decimal("0.00"),
        )

        posting_set_id = UUID(str(audit["id"])) if audit is not None else None
        audit_entry_count = int(audit["audit_entry_count"] or 0) if audit else 0
        audit_metadata_exact = True
        if audit is not None:
            audit_metadata_exact = (
                int(audit["expected_transaction_count"])
                == review_set.expected_transaction_count
                and int(audit["expected_entry_count"]) == expected_entry_count
            )
        posted = (
            posting_set_id is not None
            and audit_metadata_exact
            and audit_entry_count == expected_entry_count
            and posted_entry_count == expected_entry_count
            and draft_entry_count == 0
            and actual_entry_count == expected_entry_count
        )

        blocker: str | None = None
        if audit is not None and not posted:
            blocker = (
                "Protected Regular posting audit does not exactly match the posted review set."
            )
        elif audit is None and not review_set.draft_integrity_ready:
            blocker = review_set.blocker or (
                "Protected Regular journal drafts failed integrity review."
            )
        elif audit is None and actual_entry_count != expected_entry_count:
            blocker = "Protected Regular journal review set is incomplete."

        return RegularJournalPostingStatus(
            loan_id=loan_id,
            review_set_fingerprint=review_set_fingerprint,
            expected_transaction_count=review_set.expected_transaction_count,
            preparation_count=review_set.preparation_count,
            expected_entry_count=expected_entry_count,
            actual_entry_count=actual_entry_count,
            draft_entry_count=draft_entry_count,
            posted_entry_count=posted_entry_count,
            total_debit=total_debit,
            total_credit=total_credit,
            posting_ready=(
                audit is None
                and review_set.draft_integrity_ready
                and actual_entry_count == expected_entry_count
                and expected_entry_count > 0
            ),
            posting_blocker=blocker,
            posting_set_id=posting_set_id,
            audit_entry_count=audit_entry_count,
            posted_by_user_id=(
                UUID(str(audit["posted_by_user_id"])) if audit is not None else None
            ),
            posted_at=audit["posted_at"] if audit is not None else None,
            entry_numbers=tuple(str(row["entry_number"]) for row in entry_number_rows),
        )

    def post(
        self,
        *,
        actor_user_id: UUID,
        loan_id: UUID,
        expected_review_set_fingerprint: str,
    ) -> RegularJournalPostingStatus:
        if not self._valid_fingerprint(expected_review_set_fingerprint):
            raise RegularJournalPostingValidation(
                "The protected Regular journal review token is invalid."
            )
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        select accounting.post_regular_journal_review_set(%s, %s, %s)
                            as posting_set_id
                        """,
                        (
                            loan_id,
                            expected_review_set_fingerprint,
                            actor_user_id,
                        ),
                    )
                    cursor.fetchone()
        except psycopg.Error as error:
            raise self._map_error(error) from error

        return self.load_status(
            loan_id=loan_id,
            review_set_fingerprint=expected_review_set_fingerprint,
        )

    def _find_review_set(
        self,
        *,
        loan_id: UUID,
        review_set_fingerprint: str,
    ) -> RegularJournalDraftReviewSetStatus:
        review_sets = self._draft_repository.list_status(loan_id=loan_id)
        match = next(
            (
                item
                for item in review_sets
                if item.review_set_fingerprint == review_set_fingerprint
            ),
            None,
        )
        if match is None:
            raise RegularJournalPostingNotFound(
                "Protected Regular journal review set was not found."
            )
        return match

    @staticmethod
    def _valid_fingerprint(value: str) -> bool:
        return len(value) == 64 and all(
            character in "0123456789abcdef" for character in value
        )

    @staticmethod
    def _map_error(error: psycopg.Error) -> RegularJournalPostingError:
        message = str(error).split("CONTEXT:", 1)[0].strip()
        lowered = message.lower()
        if "was not found" in lowered:
            return RegularJournalPostingNotFound(message)
        if (
            "without the complete protected posting audit" in lowered
            or "posting audit does not match" in lowered
            or "changed" in lowered
            or "no longer" in lowered
            or "inconsistent" in lowered
            or "incomplete" in lowered
        ):
            return RegularJournalPostingConflict(message)
        if (
            "invalid" in lowered
            or "must" in lowered
            or "requires" in lowered
            or "period" in lowered
            or "account" in lowered
            or "balance" in lowered
            or "pattern" in lowered
        ):
            return RegularJournalPostingValidation(message)
        return RegularJournalPostingError(message)
