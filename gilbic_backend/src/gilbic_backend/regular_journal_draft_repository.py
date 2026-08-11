from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .database import open_connection
from .eir_cash_allocation_repository import EirCashAllocationLoanNotFound
from .eir_period_journal_api import (
    PostgresEirPeriodJournalProposalRepository,
)
from .posting_ready_evidence_review_api import (
    build_regular_posting_ready_evidence_review_api_result,
)
from .regular_cross_period_posting_ready_evidence import (
    REGULAR_CROSS_PERIOD_POSTING_READY_EVIDENCE_POLICY_VERSION,
    RegularCrossPeriodPostingReadyEvidenceBundle,
)
from .regular_journal_draft_evidence import (
    REGULAR_JOURNAL_DRAFT_POLICY_VERSION,
    RegularJournalDraftEvidenceError,
    regular_journal_draft_entries,
    regular_journal_draft_review_fingerprint,
    regular_journal_draft_review_set_fingerprint,
)


@dataclass(frozen=True, slots=True)
class RegularJournalDraftReviewBundle:
    transaction_id: UUID
    bundle_fingerprint: str
    expected_entry_count: int


@dataclass(frozen=True, slots=True)
class RegularJournalDraftReview:
    loan_id: UUID
    review_set_fingerprint: str
    evidence_policy_version: str
    draft_policy_version: str
    transaction_count: int
    bundles: tuple[RegularJournalDraftReviewBundle, ...]
    posting_eligible: bool = False
    automatic_source_posting_enabled: bool = False


@dataclass(frozen=True, slots=True)
class RegularJournalDraftEntryStatus:
    transaction_id: UUID
    sequence_order: int
    entry_type: str
    journal_entry_id: UUID
    journal_status: str
    source_type: str
    source_reference: str
    source_event_key: str
    posting_date: date
    fiscal_period_id: UUID
    fiscal_period_label: str
    fiscal_period_status: str
    line_count: int
    total_debit: Decimal
    total_credit: Decimal
    balanced: bool


@dataclass(frozen=True, slots=True)
class RegularJournalDraftPreparationStatus:
    preparation_id: UUID
    loan_id: UUID
    transaction_id: UUID
    review_set_fingerprint: str
    bundle_fingerprint: str
    evidence_policy_version: str
    draft_policy_version: str
    expected_set_transaction_count: int
    expected_entry_count: int
    prepared_by_user_id: UUID
    prepared_at: datetime
    actual_entry_count: int
    draft_entry_count: int
    posted_entry_count: int
    total_debit: Decimal
    total_credit: Decimal
    draft_integrity_ready: bool
    regular_journal_posting_enabled: bool
    automatic_source_posting_enabled: bool
    draft_integrity_blocker: str | None
    entries: tuple[RegularJournalDraftEntryStatus, ...]


@dataclass(frozen=True, slots=True)
class RegularJournalDraftReviewSetStatus:
    loan_id: UUID
    review_set_fingerprint: str
    expected_transaction_count: int
    preparation_count: int
    draft_integrity_ready: bool
    regular_journal_posting_enabled: bool
    automatic_source_posting_enabled: bool
    blocker: str | None
    preparations: tuple[RegularJournalDraftPreparationStatus, ...]


class RegularJournalDraftError(RuntimeError):
    code = "regular_journal_draft_error"


class RegularJournalDraftNotFound(RegularJournalDraftError):
    code = "regular_journal_draft_not_found"


class RegularJournalDraftConflict(RegularJournalDraftError):
    code = "regular_journal_draft_conflict"


class RegularJournalDraftValidation(RegularJournalDraftError):
    code = "regular_journal_draft_validation"


class PostgresRegularJournalDraftRepository:
    def __init__(
        self,
        *,
        evidence_repository: PostgresEirPeriodJournalProposalRepository | None = None,
    ) -> None:
        self._evidence_repository = (
            evidence_repository or PostgresEirPeriodJournalProposalRepository()
        )

    def load_review(self, *, loan_id: UUID) -> RegularJournalDraftReview:
        try:
            bundles = self._load_exact_bundles(loan_id=loan_id)
            review_set_fingerprint = regular_journal_draft_review_set_fingerprint(
                bundles
            )
            review_bundles = tuple(
                RegularJournalDraftReviewBundle(
                    transaction_id=bundle.transaction_id,
                    bundle_fingerprint=regular_journal_draft_review_fingerprint(
                        bundle
                    ),
                    expected_entry_count=len(bundle.ordered_entries),
                )
                for bundle in bundles
            )
        except RegularJournalDraftError:
            raise
        except (RegularJournalDraftEvidenceError, psycopg.Error) as error:
            raise self._map_error(error) from error

        return RegularJournalDraftReview(
            loan_id=loan_id,
            review_set_fingerprint=review_set_fingerprint,
            evidence_policy_version=(
                REGULAR_CROSS_PERIOD_POSTING_READY_EVIDENCE_POLICY_VERSION
            ),
            draft_policy_version=REGULAR_JOURNAL_DRAFT_POLICY_VERSION,
            transaction_count=len(review_bundles),
            bundles=review_bundles,
        )

    def list_status(
        self,
        *,
        loan_id: UUID,
    ) -> tuple[RegularJournalDraftReviewSetStatus, ...]:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                rows = cursor.execute(
                    """
                    select
                        review_set_fingerprint,
                        max(prepared_at) as latest_prepared_at
                    from accounting.regular_journal_draft_preparations
                    where loan_id = %s
                    group by review_set_fingerprint
                    order by latest_prepared_at desc, review_set_fingerprint
                    """,
                    (loan_id,),
                ).fetchall()
                return tuple(
                    self._load_review_set_status(
                        cursor,
                        loan_id=loan_id,
                        review_set_fingerprint=str(row["review_set_fingerprint"]),
                    )
                    for row in rows
                )

    def prepare(
        self,
        *,
        actor_user_id: UUID,
        loan_id: UUID,
        expected_review_set_fingerprint: str,
    ) -> RegularJournalDraftReviewSetStatus:
        if (
            len(expected_review_set_fingerprint) != 64
            or any(
                character not in "0123456789abcdef"
                for character in expected_review_set_fingerprint
            )
        ):
            raise RegularJournalDraftValidation(
                "The protected Regular journal review token is invalid."
            )

        # Idempotent retry path. Once drafts exist, the upstream read-only preview
        # intentionally reports draft_exists and can no longer reproduce the same
        # review set. The immutable preparation rows therefore become the retry
        # proof for an already-created exact token.
        existing = self._load_existing_review_set(
            loan_id=loan_id,
            review_set_fingerprint=expected_review_set_fingerprint,
        )
        if existing is not None:
            if not existing.draft_integrity_ready:
                raise RegularJournalDraftConflict(
                    existing.blocker
                    or "Existing protected Regular journal drafts failed integrity review."
                )
            return existing

        try:
            initial_bundles = self._load_exact_bundles(loan_id=loan_id)
            initial_fingerprint = regular_journal_draft_review_set_fingerprint(
                initial_bundles
            )
        except RegularJournalDraftError:
            raise
        except (RegularJournalDraftEvidenceError, psycopg.Error) as error:
            raise self._map_error(error) from error

        if initial_fingerprint != expected_review_set_fingerprint:
            raise RegularJournalDraftConflict(
                "Posting-ready evidence changed. Refresh the Management review before preparing protected Regular journal drafts."
            )

        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    # Serialize preparation attempts for this loan before freezing
                    # operational source tables. The second connection used by the
                    # read-only evidence loader can still SELECT through these locks.
                    cursor.execute(
                        "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
                        (f"regular-journal-draft-loan:{loan_id}",),
                    )
                    cursor.execute(
                        """
                        lock table
                            lending.loan_collection_state,
                            lending.loans,
                            lending.loan_types,
                            lending.collection_transactions
                        in share mode
                        """
                    )
                    cursor.execute(
                        """
                        lock table accounting.fiscal_periods, accounting.accounts
                        in share mode
                        """
                    )

                    # Re-check for an exact retry after waiting for another
                    # Management request on the same loan.
                    retry = self._load_review_set_status_or_none(
                        cursor,
                        loan_id=loan_id,
                        review_set_fingerprint=expected_review_set_fingerprint,
                    )
                    if retry is not None:
                        if not retry.draft_integrity_ready:
                            raise RegularJournalDraftConflict(
                                retry.blocker
                                or "Existing protected Regular journal drafts failed integrity review."
                            )
                        return retry

                    # Final TOCTOU replay while collection/fiscal/account source
                    # state is frozen. Collection writers can only continue after
                    # this transaction commits or rolls back.
                    final_bundles = self._load_exact_bundles(loan_id=loan_id)
                    final_fingerprint = regular_journal_draft_review_set_fingerprint(
                        final_bundles
                    )
                    if (
                        final_fingerprint != expected_review_set_fingerprint
                        or final_bundles != initial_bundles
                    ):
                        raise RegularJournalDraftConflict(
                            "Posting-ready evidence changed during preparation. No journal drafts were created."
                        )

                    expected_set_count = len(final_bundles)
                    for bundle in final_bundles:
                        bundle_fingerprint = (
                            regular_journal_draft_review_fingerprint(bundle)
                        )
                        entries = regular_journal_draft_entries(bundle)
                        cursor.execute(
                            """
                            select accounting.create_regular_journal_draft_batch(
                                %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb
                            ) as preparation_id
                            """,
                            (
                                loan_id,
                                bundle.transaction_id,
                                actor_user_id,
                                expected_review_set_fingerprint,
                                bundle_fingerprint,
                                REGULAR_CROSS_PERIOD_POSTING_READY_EVIDENCE_POLICY_VERSION,
                                REGULAR_JOURNAL_DRAFT_POLICY_VERSION,
                                expected_set_count,
                                Jsonb(entries),
                            ),
                        )
                        cursor.fetchone()

                    status = self._load_review_set_status(
                        cursor,
                        loan_id=loan_id,
                        review_set_fingerprint=expected_review_set_fingerprint,
                    )
                    if not status.draft_integrity_ready:
                        raise RegularJournalDraftConflict(
                            status.blocker
                            or "Protected Regular journal draft integrity verification failed."
                        )
                    return status
        except RegularJournalDraftError:
            raise
        except (RegularJournalDraftEvidenceError, psycopg.Error) as error:
            raise self._map_error(error) from error

    def _load_exact_bundles(
        self,
        *,
        loan_id: UUID,
    ) -> tuple[RegularCrossPeriodPostingReadyEvidenceBundle, ...]:
        try:
            pack, protected_fiscal_periods = self._evidence_repository.load_loan_context(
                loan_id=loan_id
            )
        except EirCashAllocationLoanNotFound as error:
            raise RegularJournalDraftNotFound(str(error)) from error
        result = build_regular_posting_ready_evidence_review_api_result(
            pack,
            protected_fiscal_periods=protected_fiscal_periods,
        )
        if result.posting_eligible or result.automatic_source_posting_enabled:
            raise RegularJournalDraftValidation(
                "Protected posting-ready evidence unexpectedly enables posting."
            )
        if result.blocker_code is not None:
            raise RegularJournalDraftValidation(
                result.blocker_message
                or "Protected posting-ready evidence is blocked."
            )
        if (
            result.status != "regular_posting_ready_evidence_review_ready"
            or not result.review_only
            or not result.bundles
        ):
            raise RegularJournalDraftValidation(
                "No exact cross-period Regular posting-ready evidence is available for draft preparation."
            )
        return result.bundles

    def _load_existing_review_set(
        self,
        *,
        loan_id: UUID,
        review_set_fingerprint: str,
    ) -> RegularJournalDraftReviewSetStatus | None:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    return self._load_review_set_status_or_none(
                        cursor,
                        loan_id=loan_id,
                        review_set_fingerprint=review_set_fingerprint,
                    )
        except psycopg.Error as error:
            raise self._map_error(error) from error

    @classmethod
    def _load_review_set_status_or_none(
        cls,
        cursor,
        *,
        loan_id: UUID,
        review_set_fingerprint: str,
    ) -> RegularJournalDraftReviewSetStatus | None:
        rows = cursor.execute(
            """
            select *
            from accounting.regular_journal_draft_preparation_status
            where loan_id = %s
              and review_set_fingerprint = %s
            order by prepared_at, transaction_id
            """,
            (loan_id, review_set_fingerprint),
        ).fetchall()
        if not rows:
            return None
        return cls._status_from_rows(cursor, rows)

    @classmethod
    def _load_review_set_status(
        cls,
        cursor,
        *,
        loan_id: UUID,
        review_set_fingerprint: str,
    ) -> RegularJournalDraftReviewSetStatus:
        status = cls._load_review_set_status_or_none(
            cursor,
            loan_id=loan_id,
            review_set_fingerprint=review_set_fingerprint,
        )
        if status is None:
            raise RegularJournalDraftNotFound(
                "Protected Regular journal draft review set was not found."
            )
        return status

    @classmethod
    def _status_from_rows(
        cls,
        cursor,
        rows,
    ) -> RegularJournalDraftReviewSetStatus:
        expected_counts = {int(row["expected_set_transaction_count"]) for row in rows}
        loan_ids = {UUID(str(row["loan_id"])) for row in rows}
        fingerprints = {str(row["review_set_fingerprint"]) for row in rows}
        if len(expected_counts) != 1 or len(loan_ids) != 1 or len(fingerprints) != 1:
            raise RegularJournalDraftConflict(
                "Protected Regular journal review-set preparation metadata is inconsistent."
            )

        preparations: list[RegularJournalDraftPreparationStatus] = []
        for row in rows:
            preparation_id = UUID(str(row["preparation_id"]))
            entry_rows = cursor.execute(
                """
                select
                    prepared.transaction_id,
                    prepared.sequence_order,
                    prepared.entry_type,
                    prepared.journal_entry_id,
                    journal.status as journal_status,
                    journal.source_type,
                    journal.source_reference,
                    journal.source_event_key,
                    journal.posting_date,
                    journal.fiscal_period_id,
                    period.label as fiscal_period_label,
                    period.status as fiscal_period_status,
                    count(line.id)::bigint as line_count,
                    coalesce(sum(line.debit), 0)::numeric(18,2) as total_debit,
                    coalesce(sum(line.credit), 0)::numeric(18,2) as total_credit
                from accounting.regular_journal_draft_preparation_entries prepared
                join accounting.journal_entries journal
                  on journal.id = prepared.journal_entry_id
                join accounting.fiscal_periods period
                  on period.id = journal.fiscal_period_id
                left join accounting.journal_lines line
                  on line.journal_entry_id = journal.id
                where prepared.preparation_id = %s
                group by
                    prepared.transaction_id,
                    prepared.sequence_order,
                    prepared.entry_type,
                    prepared.journal_entry_id,
                    journal.status,
                    journal.source_type,
                    journal.source_reference,
                    journal.source_event_key,
                    journal.posting_date,
                    journal.fiscal_period_id,
                    period.label,
                    period.status
                order by prepared.sequence_order
                """,
                (preparation_id,),
            ).fetchall()
            entries = tuple(
                RegularJournalDraftEntryStatus(
                    transaction_id=UUID(str(entry["transaction_id"])),
                    sequence_order=int(entry["sequence_order"]),
                    entry_type=str(entry["entry_type"]),
                    journal_entry_id=UUID(str(entry["journal_entry_id"])),
                    journal_status=str(entry["journal_status"]),
                    source_type=str(entry["source_type"]),
                    source_reference=str(entry["source_reference"]),
                    source_event_key=str(entry["source_event_key"]),
                    posting_date=entry["posting_date"],
                    fiscal_period_id=UUID(str(entry["fiscal_period_id"])),
                    fiscal_period_label=str(entry["fiscal_period_label"]),
                    fiscal_period_status=str(entry["fiscal_period_status"]),
                    line_count=int(entry["line_count"] or 0),
                    total_debit=Decimal(entry["total_debit"] or 0),
                    total_credit=Decimal(entry["total_credit"] or 0),
                    balanced=(
                        Decimal(entry["total_debit"] or 0) > 0
                        and Decimal(entry["total_debit"] or 0)
                        == Decimal(entry["total_credit"] or 0)
                    ),
                )
                for entry in entry_rows
            )
            preparations.append(
                RegularJournalDraftPreparationStatus(
                    preparation_id=preparation_id,
                    loan_id=UUID(str(row["loan_id"])),
                    transaction_id=UUID(str(row["transaction_id"])),
                    review_set_fingerprint=str(row["review_set_fingerprint"]),
                    bundle_fingerprint=str(row["bundle_fingerprint"]),
                    evidence_policy_version=str(row["evidence_policy_version"]),
                    draft_policy_version=str(row["draft_policy_version"]),
                    expected_set_transaction_count=int(
                        row["expected_set_transaction_count"]
                    ),
                    expected_entry_count=int(row["expected_entry_count"]),
                    prepared_by_user_id=UUID(str(row["prepared_by_user_id"])),
                    prepared_at=row["prepared_at"],
                    actual_entry_count=int(row["actual_entry_count"] or 0),
                    draft_entry_count=int(row["draft_entry_count"] or 0),
                    posted_entry_count=int(row["posted_entry_count"] or 0),
                    total_debit=Decimal(row["total_debit"] or 0),
                    total_credit=Decimal(row["total_credit"] or 0),
                    draft_integrity_ready=bool(row["draft_integrity_ready"]),
                    regular_journal_posting_enabled=bool(
                        row["regular_journal_posting_enabled"]
                    ),
                    automatic_source_posting_enabled=bool(
                        row["automatic_source_posting_enabled"]
                    ),
                    draft_integrity_blocker=(
                        str(row["draft_integrity_blocker"])
                        if row["draft_integrity_blocker"]
                        else None
                    ),
                    entries=entries,
                )
            )

        expected_count = expected_counts.pop()
        preparation_count = len(preparations)
        blocker: str | None = None
        if preparation_count != expected_count:
            blocker = (
                "Protected Regular journal review set is incomplete: prepared "
                f"{preparation_count} of {expected_count} transactions."
            )
        else:
            failed = next(
                (
                    item
                    for item in preparations
                    if not item.draft_integrity_ready
                    or item.regular_journal_posting_enabled
                    or item.automatic_source_posting_enabled
                ),
                None,
            )
            if failed is not None:
                blocker = (
                    failed.draft_integrity_blocker
                    or "One or more protected Regular journal drafts failed integrity review."
                )

        return RegularJournalDraftReviewSetStatus(
            loan_id=loan_ids.pop(),
            review_set_fingerprint=fingerprints.pop(),
            expected_transaction_count=expected_count,
            preparation_count=preparation_count,
            draft_integrity_ready=(blocker is None),
            regular_journal_posting_enabled=False,
            automatic_source_posting_enabled=False,
            blocker=blocker,
            preparations=tuple(preparations),
        )

    @staticmethod
    def _map_error(error: Exception) -> RegularJournalDraftError:
        message = str(error).split("CONTEXT:", 1)[0].strip()
        lowered = message.lower()
        if "was not found" in lowered:
            return RegularJournalDraftNotFound(message)
        if (
            "already have a journal" in lowered
            or "does not match the reviewed evidence" in lowered
            or "changed" in lowered
            or "no longer" in lowered
            or "outside" in lowered
        ):
            return RegularJournalDraftConflict(message)
        if (
            "requires" in lowered
            or "must" in lowered
            or "invalid" in lowered
            or "malformed" in lowered
            or "blocked" in lowered
            or "unknown" in lowered
            or "inactive" in lowered
            or "non-posting" in lowered
            or "not exact" in lowered
            or "not available" in lowered
            or "does not belong" in lowered
            or "only a non-voided" in lowered
            or "pattern" in lowered
            or "balanced" in lowered
        ):
            return RegularJournalDraftValidation(message)
        return RegularJournalDraftError(message)
