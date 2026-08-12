from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .database import open_connection
from .greenfield_regular_ledger_reconciliation_repository import (
    GreenfieldRegularLedgerReconciliationPreview,
    PostgresGreenfieldRegularLedgerReconciliationRepository,
)


BOUNDARY_POLICY_VERSION = "greenfield_regular_renewal_boundary_eir_v1"
DRAFT_POLICY_VERSION = "renewal_boundary_eir_journal_draft_v1"
POSTING_POLICY_VERSION = "renewal_boundary_eir_journal_posting_v1"
BOUNDARY_BLOCKER = "renewal_boundary_eir_accrual_not_posted"


@dataclass(frozen=True, slots=True)
class RenewalBoundaryEirJournalReviewEntry:
    sequence_order: int
    fiscal_period_id: UUID
    fiscal_period_label: str
    accrual_start_date_inclusive: date
    accrual_end_date_inclusive: date
    posting_date: date
    day_count: int
    amount: Decimal
    source_type: str
    source_reference: str
    source_event_key: str
    debit_account_system_key: str
    credit_account_system_key: str


@dataclass(frozen=True, slots=True)
class RenewalBoundaryEirJournalReview:
    renewal_execution_event_id: UUID
    old_loan_id: UUID
    old_loan_number: str
    client_id: UUID
    client_code: str
    client_name: str
    target_date: date
    expected_entry_count: int
    total_debit: Decimal
    total_credit: Decimal
    protected_source_journal_count: int
    exact_protected_source_journal_count: int
    ledger_loan_component_through_last_source: Decimal
    ledger_accrued_interest_through_last_source: Decimal
    ledger_gross_carrying_through_last_source: Decimal
    target_loan_component: Decimal
    target_accrued_interest_component: Decimal
    target_gross_carrying_amount: Decimal
    tail_effective_interest_accrued: Decimal
    boundary_policy_version: str
    draft_policy_version: str
    posting_policy_version: str
    entries: tuple[RenewalBoundaryEirJournalReviewEntry, ...]
    review_token: str
    posting_enabled: bool = False
    automatic_source_posting: bool = False


@dataclass(frozen=True, slots=True)
class RenewalBoundaryEirJournalStatusEntry:
    sequence_order: int
    journal_entry_id: UUID
    fiscal_period_id: UUID
    posting_date: date
    amount: Decimal
    source_reference: str
    source_event_key: str
    journal_status: str
    entry_number: str | None


@dataclass(frozen=True, slots=True)
class RenewalBoundaryEirJournalStatus:
    preparation_id: UUID
    renewal_execution_event_id: UUID
    old_loan_id: UUID
    client_id: UUID
    target_date: date
    review_token: str
    boundary_policy_version: str
    draft_policy_version: str
    expected_entry_count: int
    total_amount: Decimal
    prepared_by_user_id: UUID
    prepared_at: datetime
    posting_set_id: UUID | None
    posting_policy_version: str | None
    posted_by_user_id: UUID | None
    posted_at: datetime | None
    actual_entry_count: int
    draft_entry_count: int
    posted_entry_count: int
    total_debit: Decimal
    total_credit: Decimal
    posting_audit_entry_count: int
    integrity_ready: bool
    protected_posting_complete: bool
    automatic_source_posting: bool
    entries: tuple[RenewalBoundaryEirJournalStatusEntry, ...]


class RenewalBoundaryEirJournalError(RuntimeError):
    code = "renewal_boundary_eir_journal_error"


class RenewalBoundaryEirJournalNotFound(RenewalBoundaryEirJournalError):
    code = "renewal_boundary_eir_journal_not_found"


class RenewalBoundaryEirJournalConflict(RenewalBoundaryEirJournalError):
    code = "renewal_boundary_eir_journal_conflict"


class RenewalBoundaryEirJournalValidation(RenewalBoundaryEirJournalError):
    code = "renewal_boundary_eir_journal_validation"


def _money(value: object) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _review_token(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _token_is_valid(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


class PostgresRenewalBoundaryEirJournalRepository:
    def __init__(
        self,
        *,
        reconciliation_repository: PostgresGreenfieldRegularLedgerReconciliationRepository
        | None = None,
    ) -> None:
        self._reconciliation_repository = (
            reconciliation_repository
            or PostgresGreenfieldRegularLedgerReconciliationRepository()
        )

    def load_review(
        self,
        *,
        renewal_execution_event_id: UUID,
    ) -> RenewalBoundaryEirJournalReview:
        records = self._reconciliation_repository.list_previews(
            renewal_execution_event_id=renewal_execution_event_id,
            limit=2,
        )
        if len(records) != 1:
            if not records:
                raise RenewalBoundaryEirJournalNotFound(
                    "Authoritative greenfield Regular renewal reconciliation evidence was not found."
                )
            raise RenewalBoundaryEirJournalConflict(
                "More than one protected renewal reconciliation record matched the execution evidence."
            )
        return self._review_from_reconciliation(records[0])

    def load_status(
        self,
        *,
        renewal_execution_event_id: UUID,
    ) -> RenewalBoundaryEirJournalStatus | None:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    return self._load_status_in_cursor(
                        cursor,
                        renewal_execution_event_id=renewal_execution_event_id,
                    )
        except psycopg.Error as error:
            raise self._map_error(error) from error

    def prepare(
        self,
        *,
        actor_user_id: UUID,
        renewal_execution_event_id: UUID,
        expected_review_token: str,
    ) -> RenewalBoundaryEirJournalStatus:
        normalized_token = expected_review_token.strip().lower()
        if not _token_is_valid(normalized_token):
            raise RenewalBoundaryEirJournalValidation(
                "The protected renewal-boundary EIR review token is invalid."
            )

        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    self._lock_exact_review_sources(
                        cursor,
                        renewal_execution_event_id=renewal_execution_event_id,
                    )
                    review = self.load_review(
                        renewal_execution_event_id=renewal_execution_event_id,
                    )
                    if review.review_token != normalized_token:
                        raise RenewalBoundaryEirJournalConflict(
                            "Renewal-boundary EIR evidence changed. Refresh the Management review before preparing protected drafts."
                        )

                    existing = self._load_status_in_cursor(
                        cursor,
                        renewal_execution_event_id=renewal_execution_event_id,
                    )
                    if existing is not None:
                        if existing.review_token != normalized_token:
                            raise RenewalBoundaryEirJournalConflict(
                                "An existing protected renewal-boundary EIR preparation was created from different reviewed evidence."
                            )
                        if not existing.integrity_ready:
                            raise RenewalBoundaryEirJournalConflict(
                                "The existing protected renewal-boundary EIR journal set failed immutable integrity review."
                            )
                        return existing

                    entries = [self._entry_payload(entry) for entry in review.entries]
                    row = cursor.execute(
                        """
                        select accounting.create_renewal_boundary_eir_journal_draft_batch(
                            %s, %s, %s, %s, %s, %s, %s::jsonb
                        ) as preparation_id
                        """,
                        (
                            renewal_execution_event_id,
                            actor_user_id,
                            normalized_token,
                            BOUNDARY_POLICY_VERSION,
                            DRAFT_POLICY_VERSION,
                            review.total_debit,
                            Jsonb(entries),
                        ),
                    ).fetchone()
                    if row is None or row["preparation_id"] is None:
                        raise RenewalBoundaryEirJournalConflict(
                            "Protected renewal-boundary EIR preparation returned no immutable preparation record."
                        )
                    status = self._load_status_in_cursor(
                        cursor,
                        renewal_execution_event_id=renewal_execution_event_id,
                    )
                    if status is None or status.preparation_id != UUID(
                        str(row["preparation_id"])
                    ):
                        raise RenewalBoundaryEirJournalConflict(
                            "Protected renewal-boundary EIR status was not found after preparation."
                        )
                    if (
                        not status.integrity_ready
                        or status.review_token != normalized_token
                        or status.expected_entry_count != review.expected_entry_count
                        or status.total_debit != review.total_debit
                        or status.total_credit != review.total_credit
                    ):
                        raise RenewalBoundaryEirJournalConflict(
                            "Protected renewal-boundary EIR draft failed its post-create integrity check."
                        )
                    return status
        except RenewalBoundaryEirJournalError:
            raise
        except psycopg.Error as error:
            raise self._map_error(error) from error

    def post(
        self,
        *,
        actor_user_id: UUID,
        renewal_execution_event_id: UUID,
        expected_review_token: str,
        expected_entry_count: int,
        expected_total_debit: Decimal,
        expected_total_credit: Decimal,
    ) -> RenewalBoundaryEirJournalStatus:
        normalized_token = expected_review_token.strip().lower()
        if not _token_is_valid(normalized_token):
            raise RenewalBoundaryEirJournalValidation(
                "The protected renewal-boundary EIR review token is invalid."
            )
        debit = _money(expected_total_debit)
        credit = _money(expected_total_credit)
        if expected_entry_count < 1 or debit <= 0 or debit != credit:
            raise RenewalBoundaryEirJournalValidation(
                "The protected renewal-boundary EIR posting confirmation is invalid."
            )

        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    self._lock_exact_review_sources(
                        cursor,
                        renewal_execution_event_id=renewal_execution_event_id,
                    )
                    review = self.load_review(
                        renewal_execution_event_id=renewal_execution_event_id,
                    )
                    if (
                        review.review_token != normalized_token
                        or review.expected_entry_count != expected_entry_count
                        or review.total_debit != debit
                        or review.total_credit != credit
                    ):
                        raise RenewalBoundaryEirJournalConflict(
                            "Renewal-boundary EIR posting confirmation is stale. Refresh the exact Management review before posting."
                        )

                    status_before = self._load_status_in_cursor(
                        cursor,
                        renewal_execution_event_id=renewal_execution_event_id,
                    )
                    if status_before is None:
                        raise RenewalBoundaryEirJournalNotFound(
                            "Prepare the protected renewal-boundary EIR journal drafts before posting."
                        )
                    if status_before.review_token != normalized_token:
                        raise RenewalBoundaryEirJournalConflict(
                            "Protected renewal-boundary EIR preparation does not match the reviewed posting confirmation."
                        )
                    if not status_before.integrity_ready:
                        raise RenewalBoundaryEirJournalConflict(
                            "Protected renewal-boundary EIR preparation failed immutable integrity review before posting."
                        )

                    cursor.execute(
                        """
                        select accounting.post_renewal_boundary_eir_journal_review_set(
                            %s, %s, %s, %s, %s, %s, %s
                        ) as posting_set_id
                        """,
                        (
                            renewal_execution_event_id,
                            actor_user_id,
                            normalized_token,
                            expected_entry_count,
                            debit,
                            credit,
                            POSTING_POLICY_VERSION,
                        ),
                    ).fetchone()

                    status = self._load_status_in_cursor(
                        cursor,
                        renewal_execution_event_id=renewal_execution_event_id,
                    )
                    if status is None or not status.protected_posting_complete:
                        raise RenewalBoundaryEirJournalConflict(
                            "Protected renewal-boundary EIR posting did not produce a complete immutable posting audit."
                        )
                    if (
                        status.posting_policy_version != POSTING_POLICY_VERSION
                        or status.posted_entry_count != expected_entry_count
                        or status.posting_audit_entry_count != expected_entry_count
                        or status.total_debit != debit
                        or status.total_credit != credit
                    ):
                        raise RenewalBoundaryEirJournalConflict(
                            "Protected renewal-boundary EIR posting audit does not match the confirmed review set."
                        )
                    return status
        except RenewalBoundaryEirJournalError:
            raise
        except psycopg.Error as error:
            raise self._map_error(error) from error

    @staticmethod
    def _lock_exact_review_sources(cursor, *, renewal_execution_event_id: UUID) -> None:
        cursor.execute(
            "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (f"renewal-boundary-eir-journal:{renewal_execution_event_id}",),
        )
        cursor.execute(
            """
            LOCK TABLE
                lending.loan_renewal_execution_events,
                lending.loan_disbursement_events,
                lending.loans,
                lending.loan_types,
                lending.clients,
                lending.collection_transactions,
                lending.loan_contract_schedules,
                lending.loan_contract_schedule_registrations,
                lending.loan_contract_installments,
                accounting.loan_disbursement_journal_postings,
                accounting.loan_disbursement_journal_reversals,
                lending.loan_disbursement_cancellations,
                accounting.regular_journal_draft_preparations,
                accounting.regular_journal_draft_preparation_entries,
                accounting.regular_journal_posting_sets,
                accounting.regular_journal_posting_entries,
                accounting.regular_journal_reversal_sets,
                accounting.regular_journal_reversal_entries,
                accounting.journal_entries,
                accounting.journal_lines,
                accounting.fiscal_periods,
                accounting.accounts,
                accounting.renewal_boundary_eir_journal_preparations,
                accounting.renewal_boundary_eir_journal_preparation_entries,
                accounting.renewal_boundary_eir_journal_posting_sets,
                accounting.renewal_boundary_eir_journal_posting_entries
            IN SHARE MODE
            """
        )

    @staticmethod
    def _entry_payload(entry: RenewalBoundaryEirJournalReviewEntry) -> dict[str, object]:
        return {
            "sequence_order": entry.sequence_order,
            "fiscal_period_id": str(entry.fiscal_period_id),
            "posting_date": entry.posting_date.isoformat(),
            "amount": format(entry.amount, ".2f"),
            "source_type": entry.source_type,
            "source_reference": entry.source_reference,
            "source_event_key": entry.source_event_key,
            "debit_account_system_key": entry.debit_account_system_key,
            "credit_account_system_key": entry.credit_account_system_key,
        }

    @staticmethod
    def _review_from_reconciliation(
        record: GreenfieldRegularLedgerReconciliationPreview,
    ) -> RenewalBoundaryEirJournalReview:
        reconciliation = record.reconciliation
        boundary = record.renewal_boundary_eir_preview
        if reconciliation is None:
            raise RenewalBoundaryEirJournalValidation(
                "Exact protected old-loan ledger reconciliation is required before renewal-boundary EIR preparation."
            )
        if (
            reconciliation.blocker_code != BOUNDARY_BLOCKER
            or not reconciliation.protected_regular_journals_reconciled
            or reconciliation.accounting_carrying_amount_ready
        ):
            raise RenewalBoundaryEirJournalValidation(
                "Renewal-boundary EIR preparation is permitted only when protected Regular source journals reconcile exactly and the boundary accrual is the sole remaining carrying-amount blocker."
            )
        if (
            boundary is None
            or boundary.disposition != "renewal_boundary_eir_journal_preview_ready"
            or boundary.blocker_code is not None
            or not boundary.balanced
            or boundary.posting_eligible
            or boundary.automatic_source_posting
            or boundary.amount <= 0
            or not boundary.period_proposals
        ):
            raise RenewalBoundaryEirJournalValidation(
                "Exact read-only renewal-boundary EIR journal coordinates are not ready."
            )
        if boundary.renewal_execution_event_id != record.renewal_execution_event_id:
            raise RenewalBoundaryEirJournalValidation(
                "Renewal-boundary EIR preview execution identity does not match the authoritative renewal reconciliation."
            )

        required_values = (
            reconciliation.ledger_loan_component_through_last_source,
            reconciliation.ledger_accrued_interest_through_last_source,
            reconciliation.ledger_gross_carrying_through_last_source,
            reconciliation.target_loan_component,
            reconciliation.target_accrued_interest_component,
            reconciliation.target_gross_carrying_amount,
        )
        if any(value is None for value in required_values):
            raise RenewalBoundaryEirJournalValidation(
                "Complete old-loan ledger and target carrying components are required before boundary preparation."
            )

        entries: list[RenewalBoundaryEirJournalReviewEntry] = []
        for sequence_order, proposal in enumerate(boundary.period_proposals, start=1):
            if (
                len(proposal.proposed_lines) != 2
                or proposal.source_type != "regular_renewal_eir_accrual"
            ):
                raise RenewalBoundaryEirJournalValidation(
                    "Renewal-boundary EIR period coordinates are not the protected two-line Regular EIR pattern."
                )
            debit = next(
                (
                    line
                    for line in proposal.proposed_lines
                    if line.account_system_key == "accrued_interest_receivable"
                    and line.side == "debit"
                ),
                None,
            )
            credit = next(
                (
                    line
                    for line in proposal.proposed_lines
                    if line.account_system_key == "interest_income_regular"
                    and line.side == "credit"
                ),
                None,
            )
            if (
                debit is None
                or credit is None
                or debit.amount != proposal.amount
                or credit.amount != proposal.amount
                or proposal.amount <= 0
            ):
                raise RenewalBoundaryEirJournalValidation(
                    "Renewal-boundary EIR period lines do not reconcile exactly to the approved amount."
                )
            entries.append(
                RenewalBoundaryEirJournalReviewEntry(
                    sequence_order=sequence_order,
                    fiscal_period_id=proposal.fiscal_period_id,
                    fiscal_period_label=proposal.fiscal_period_label,
                    accrual_start_date_inclusive=proposal.accrual_start_date_inclusive,
                    accrual_end_date_inclusive=proposal.accrual_end_date_inclusive,
                    posting_date=proposal.posting_date,
                    day_count=proposal.day_count,
                    amount=_money(proposal.amount),
                    source_type=proposal.source_type,
                    source_reference=proposal.source_reference,
                    source_event_key=proposal.source_event_key,
                    debit_account_system_key="accrued_interest_receivable",
                    credit_account_system_key="interest_income_regular",
                )
            )

        total = sum((entry.amount for entry in entries), Decimal("0.00"))
        total = _money(total)
        if total != _money(boundary.amount) or total <= 0:
            raise RenewalBoundaryEirJournalValidation(
                "Renewal-boundary EIR period amounts do not reconcile to the protected tail amount."
            )

        token_payload: dict[str, object] = {
            "boundary_policy_version": BOUNDARY_POLICY_VERSION,
            "draft_policy_version": DRAFT_POLICY_VERSION,
            "posting_policy_version": POSTING_POLICY_VERSION,
            "renewal_execution_event_id": str(record.renewal_execution_event_id),
            "old_loan_id": str(record.old_loan_id),
            "client_id": str(record.client_id),
            "target_date": record.target_date.isoformat(),
            "expected_active_transaction_count": (
                reconciliation.expected_active_transaction_count
            ),
            "expected_source_journal_count": reconciliation.expected_journal_count,
            "exact_posted_source_journal_count": (
                reconciliation.exact_posted_journal_count
            ),
            "ledger_loan_component_through_last_source": format(
                _money(reconciliation.ledger_loan_component_through_last_source),
                ".2f",
            ),
            "ledger_accrued_interest_through_last_source": format(
                _money(reconciliation.ledger_accrued_interest_through_last_source),
                ".2f",
            ),
            "ledger_gross_carrying_through_last_source": format(
                _money(reconciliation.ledger_gross_carrying_through_last_source),
                ".2f",
            ),
            "target_loan_component": format(
                _money(reconciliation.target_loan_component), ".2f"
            ),
            "target_accrued_interest_component": format(
                _money(reconciliation.target_accrued_interest_component), ".2f"
            ),
            "target_gross_carrying_amount": format(
                _money(reconciliation.target_gross_carrying_amount), ".2f"
            ),
            "tail_effective_interest_accrued": format(
                _money(reconciliation.tail_effective_interest_accrued), ".2f"
            ),
            "entries": [
                {
                    "sequence_order": entry.sequence_order,
                    "fiscal_period_id": str(entry.fiscal_period_id),
                    "fiscal_period_label": entry.fiscal_period_label,
                    "accrual_start_date_inclusive": (
                        entry.accrual_start_date_inclusive.isoformat()
                    ),
                    "accrual_end_date_inclusive": (
                        entry.accrual_end_date_inclusive.isoformat()
                    ),
                    "posting_date": entry.posting_date.isoformat(),
                    "day_count": entry.day_count,
                    "amount": format(entry.amount, ".2f"),
                    "source_type": entry.source_type,
                    "source_reference": entry.source_reference,
                    "source_event_key": entry.source_event_key,
                    "debit_account_system_key": entry.debit_account_system_key,
                    "credit_account_system_key": entry.credit_account_system_key,
                }
                for entry in entries
            ],
        }
        token = _review_token(token_payload)

        return RenewalBoundaryEirJournalReview(
            renewal_execution_event_id=record.renewal_execution_event_id,
            old_loan_id=record.old_loan_id,
            old_loan_number=record.old_loan_number,
            client_id=record.client_id,
            client_code=record.client_code,
            client_name=record.client_name,
            target_date=record.target_date,
            expected_entry_count=len(entries),
            total_debit=total,
            total_credit=total,
            protected_source_journal_count=reconciliation.expected_journal_count,
            exact_protected_source_journal_count=(
                reconciliation.exact_posted_journal_count
            ),
            ledger_loan_component_through_last_source=_money(
                reconciliation.ledger_loan_component_through_last_source
            ),
            ledger_accrued_interest_through_last_source=_money(
                reconciliation.ledger_accrued_interest_through_last_source
            ),
            ledger_gross_carrying_through_last_source=_money(
                reconciliation.ledger_gross_carrying_through_last_source
            ),
            target_loan_component=_money(reconciliation.target_loan_component),
            target_accrued_interest_component=_money(
                reconciliation.target_accrued_interest_component
            ),
            target_gross_carrying_amount=_money(
                reconciliation.target_gross_carrying_amount
            ),
            tail_effective_interest_accrued=_money(
                reconciliation.tail_effective_interest_accrued
            ),
            boundary_policy_version=BOUNDARY_POLICY_VERSION,
            draft_policy_version=DRAFT_POLICY_VERSION,
            posting_policy_version=POSTING_POLICY_VERSION,
            entries=tuple(entries),
            review_token=token,
        )

    @staticmethod
    def _load_status_in_cursor(
        cursor,
        *,
        renewal_execution_event_id: UUID,
    ) -> RenewalBoundaryEirJournalStatus | None:
        row = cursor.execute(
            """
            select *
            from accounting.renewal_boundary_eir_journal_status
            where renewal_execution_event_id = %s
            """,
            (renewal_execution_event_id,),
        ).fetchone()
        if row is None:
            return None
        entry_rows = cursor.execute(
            """
            select
                prepared_entry.sequence_order,
                prepared_entry.journal_entry_id,
                prepared_entry.fiscal_period_id,
                prepared_entry.posting_date,
                prepared_entry.amount,
                prepared_entry.source_reference,
                prepared_entry.source_event_key,
                journal.status as journal_status,
                journal.entry_number
            from accounting.renewal_boundary_eir_journal_preparation_entries prepared_entry
            join accounting.journal_entries journal
              on journal.id = prepared_entry.journal_entry_id
            where prepared_entry.preparation_id = %s
            order by prepared_entry.sequence_order
            """,
            (row["preparation_id"],),
        ).fetchall()
        entries = tuple(
            RenewalBoundaryEirJournalStatusEntry(
                sequence_order=int(entry["sequence_order"]),
                journal_entry_id=UUID(str(entry["journal_entry_id"])),
                fiscal_period_id=UUID(str(entry["fiscal_period_id"])),
                posting_date=entry["posting_date"],
                amount=_money(entry["amount"]),
                source_reference=str(entry["source_reference"]),
                source_event_key=str(entry["source_event_key"]),
                journal_status=str(entry["journal_status"]),
                entry_number=(
                    None if entry["entry_number"] is None else str(entry["entry_number"])
                ),
            )
            for entry in entry_rows
        )
        return RenewalBoundaryEirJournalStatus(
            preparation_id=UUID(str(row["preparation_id"])),
            renewal_execution_event_id=UUID(str(row["renewal_execution_event_id"])),
            old_loan_id=UUID(str(row["old_loan_id"])),
            client_id=UUID(str(row["client_id"])),
            target_date=row["target_date"],
            review_token=str(row["review_token"]),
            boundary_policy_version=str(row["boundary_policy_version"]),
            draft_policy_version=str(row["draft_policy_version"]),
            expected_entry_count=int(row["expected_entry_count"]),
            total_amount=_money(row["total_amount"]),
            prepared_by_user_id=UUID(str(row["prepared_by_user_id"])),
            prepared_at=row["prepared_at"],
            posting_set_id=(
                None
                if row["posting_set_id"] is None
                else UUID(str(row["posting_set_id"]))
            ),
            posting_policy_version=(
                None
                if row["posting_policy_version"] is None
                else str(row["posting_policy_version"])
            ),
            posted_by_user_id=(
                None
                if row["posted_by_user_id"] is None
                else UUID(str(row["posted_by_user_id"]))
            ),
            posted_at=row["posted_at"],
            actual_entry_count=int(row["actual_entry_count"]),
            draft_entry_count=int(row["draft_entry_count"]),
            posted_entry_count=int(row["posted_entry_count"]),
            total_debit=_money(row["total_debit"]),
            total_credit=_money(row["total_credit"]),
            posting_audit_entry_count=int(row["posting_audit_entry_count"]),
            integrity_ready=bool(row["integrity_ready"]),
            protected_posting_complete=bool(row["protected_posting_complete"]),
            automatic_source_posting=bool(row["automatic_source_posting"]),
            entries=entries,
        )

    @staticmethod
    def _map_error(error: psycopg.Error) -> RenewalBoundaryEirJournalError:
        message = str(error).split("CONTEXT:", 1)[0].strip()
        lowered = message.lower()
        if "not found" in lowered:
            return RenewalBoundaryEirJournalNotFound(message)
        if any(
            marker in lowered
            for marker in (
                "changed",
                "already",
                "existing protected",
                "incomplete",
                "integrity",
                "stale",
                "does not match",
                "without the complete",
            )
        ):
            return RenewalBoundaryEirJournalConflict(message)
        return RenewalBoundaryEirJournalValidation(
            message or "Protected renewal-boundary EIR journal operation failed."
        )