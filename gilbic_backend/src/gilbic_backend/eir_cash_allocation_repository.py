from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from psycopg.rows import dict_row

from .database import open_connection
from .eir_cash_allocation import (
    EirAllocationResult,
    EirCashSourceEvent,
    EirCutoverState,
    allocate_event_date_eir_cash,
)
from .regular_collection_journal_preview import (
    REGULAR_COLLECTION_ACCOUNT_KEYS,
    RegularCollectionJournalPreview,
    build_regular_collection_journal_preview,
)
from .regular_eir_accrual_journal_preview import (
    REGULAR_EIR_ACCRUAL_ACCOUNT_KEYS,
    AccountingFiscalPeriodReference,
    RegularEirAccrualJournalPreview,
    build_regular_eir_accrual_journal_preview,
)


MAX_SOURCE_EVENTS = 5000
PROTECTED_MEASUREMENT_POLICY_VERSION = "eir_cutover_v1"


class EirCashAllocationError(RuntimeError):
    code = "eir_cash_allocation_error"


class EirCashAllocationLoanNotFound(EirCashAllocationError):
    code = "eir_cash_allocation_loan_not_found"


@dataclass(frozen=True, slots=True)
class EirCashAllocationPack:
    loan_id: UUID
    loan_number: str
    client_name: str
    cutover_date: date | None
    opening_balance_prepared: bool
    opening_balance_posted: bool
    opening_balance_entry_number: str | None
    source_event_count: int
    source_history_complete: bool
    blocker_code: str | None
    blocker_message: str | None
    allocation: EirAllocationResult | None
    protected_snapshot_available: bool = False
    protected_snapshot_reconciled: bool = False
    protected_snapshot_blocker: str | None = None
    automatic_source_posting_enabled: bool = False
    account_configuration_ready: bool = False
    account_configuration_blocker: str | None = None
    eir_accrual_account_configuration_ready: bool = False
    eir_accrual_account_configuration_blocker: str | None = None
    eir_accrual_previews: tuple[RegularEirAccrualJournalPreview, ...] = ()
    collection_journal_previews: tuple[RegularCollectionJournalPreview, ...] = ()


class PostgresEirCashAllocationRepository:
    def load_loan_allocation(self, *, loan_id: UUID) -> EirCashAllocationPack:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select
                        l.loan_number,
                        c.full_name as client_name
                    from lending.loans l
                    join lending.clients c on c.id = l.client_id
                    where l.id = %s
                    """,
                    (loan_id,),
                )
                loan = cursor.fetchone()
                if loan is None:
                    raise EirCashAllocationLoanNotFound("Loan was not found.")

                (
                    account_configuration_ready,
                    account_configuration_blocker,
                ) = self._account_configuration(
                    cursor,
                    required_keys=REGULAR_COLLECTION_ACCOUNT_KEYS,
                    label="Regular collection",
                )
                (
                    eir_accrual_account_configuration_ready,
                    eir_accrual_account_configuration_blocker,
                ) = self._account_configuration(
                    cursor,
                    required_keys=REGULAR_EIR_ACCRUAL_ACCOUNT_KEYS,
                    label="Regular EIR accrual",
                )
                cutover = self._load_current_cutover(cursor)
                if cutover is None:
                    return self._blocked_pack(
                        loan_id=loan_id,
                        loan=loan,
                        cutover_date=None,
                        opening_balance_prepared=False,
                        opening_balance_posted=False,
                        opening_balance_entry_number=None,
                        blocker_code="cutover_required",
                        blocker_message="Create and verify the protected opening-balance cutover before event-date EIR allocation.",
                        account_configuration_ready=account_configuration_ready,
                        account_configuration_blocker=account_configuration_blocker,
                        eir_accrual_account_configuration_ready=eir_accrual_account_configuration_ready,
                        eir_accrual_account_configuration_blocker=eir_accrual_account_configuration_blocker,
                    )

                workbook_id = UUID(str(cutover["workbook_id"]))
                cutover_date = cutover["cutover_date"]
                opening_balance_prepared = bool(cutover["opening_balance_prepared"])
                opening_balance_posted = bool(cutover["opening_balance_posted"])
                opening_balance_entry_number = (
                    str(cutover["opening_balance_entry_number"])
                    if cutover["opening_balance_entry_number"]
                    else None
                )

                protected_snapshot_available = False
                protected_snapshot_reconciled = False
                protected_snapshot_blocker: str | None = None

                if opening_balance_prepared:
                    reconciliation = self._load_snapshot_reconciliation(
                        cursor,
                        workbook_id=workbook_id,
                    )
                    measurement = self._load_protected_snapshot(
                        cursor,
                        workbook_id=workbook_id,
                        loan_id=loan_id,
                    )
                    protected_snapshot_available = measurement is not None
                    protected_snapshot_reconciled = bool(
                        reconciliation is not None
                        and reconciliation["ledger_anchor_ready"]
                    )
                    protected_snapshot_blocker = (
                        str(reconciliation["ledger_anchor_blocker"])
                        if reconciliation is not None
                        and reconciliation["ledger_anchor_blocker"]
                        else None
                    )

                    if reconciliation is None or measurement is None:
                        return self._blocked_pack(
                            loan_id=loan_id,
                            loan=loan,
                            cutover_date=cutover_date,
                            opening_balance_prepared=True,
                            opening_balance_posted=opening_balance_posted,
                            opening_balance_entry_number=opening_balance_entry_number,
                            blocker_code="protected_cutover_snapshot_required",
                            blocker_message=(
                                "The opening-balance journal is prepared but this loan "
                                "does not have the required immutable cutover EIR "
                                "snapshot batch. Mutable Stage 5D remeasurement is not "
                                "used after preparation."
                            ),
                            protected_snapshot_available=protected_snapshot_available,
                            protected_snapshot_reconciled=False,
                            protected_snapshot_blocker=protected_snapshot_blocker,
                            account_configuration_ready=account_configuration_ready,
                            account_configuration_blocker=account_configuration_blocker,
                            eir_accrual_account_configuration_ready=eir_accrual_account_configuration_ready,
                            eir_accrual_account_configuration_blocker=eir_accrual_account_configuration_blocker,
                        )

                    if (
                        str(reconciliation["measurement_policy_version"])
                        != PROTECTED_MEASUREMENT_POLICY_VERSION
                    ):
                        return self._blocked_pack(
                            loan_id=loan_id,
                            loan=loan,
                            cutover_date=cutover_date,
                            opening_balance_prepared=True,
                            opening_balance_posted=opening_balance_posted,
                            opening_balance_entry_number=opening_balance_entry_number,
                            blocker_code="protected_cutover_snapshot_policy_mismatch",
                            blocker_message="Protected cutover snapshot policy version is not supported by this allocator.",
                            protected_snapshot_available=True,
                            protected_snapshot_reconciled=False,
                            protected_snapshot_blocker="Unsupported protected snapshot policy version.",
                            account_configuration_ready=account_configuration_ready,
                            account_configuration_blocker=account_configuration_blocker,
                            eir_accrual_account_configuration_ready=eir_accrual_account_configuration_ready,
                            eir_accrual_account_configuration_blocker=eir_accrual_account_configuration_blocker,
                        )

                    if not protected_snapshot_reconciled:
                        return self._blocked_pack(
                            loan_id=loan_id,
                            loan=loan,
                            cutover_date=cutover_date,
                            opening_balance_prepared=True,
                            opening_balance_posted=opening_balance_posted,
                            opening_balance_entry_number=opening_balance_entry_number,
                            blocker_code="protected_cutover_snapshot_not_reconciled",
                            blocker_message=(
                                protected_snapshot_blocker
                                or "Protected cutover snapshots do not reconcile to the prepared opening journal."
                            ),
                            protected_snapshot_available=True,
                            protected_snapshot_reconciled=False,
                            protected_snapshot_blocker=protected_snapshot_blocker,
                            account_configuration_ready=account_configuration_ready,
                            account_configuration_blocker=account_configuration_blocker,
                            eir_accrual_account_configuration_ready=eir_accrual_account_configuration_ready,
                            eir_accrual_account_configuration_blocker=eir_accrual_account_configuration_blocker,
                        )
                else:
                    cursor.execute(
                        """
                        select count(*) as same_day_cash_count
                        from lending.collection_transactions t
                        where t.loan_id = %s
                          and t.collection_date = %s
                          and t.is_voided = false
                          and t.entry_type in ('payment', 'advance')
                          and t.amount > 0
                        """,
                        (loan_id, cutover_date),
                    )
                    same_day_cash_count = int(cursor.fetchone()["same_day_cash_count"])
                    if same_day_cash_count > 0:
                        return self._blocked_pack(
                            loan_id=loan_id,
                            loan=loan,
                            cutover_date=cutover_date,
                            opening_balance_prepared=False,
                            opening_balance_posted=False,
                            opening_balance_entry_number=None,
                            blocker_code="cutover_date_cash_review",
                            blocker_message="Cash exists on the date-only cutover boundary. Confirm whether it is included in the protected opening balance before rolling forward post-cutover EIR.",
                            account_configuration_ready=account_configuration_ready,
                            account_configuration_blocker=account_configuration_blocker,
                            eir_accrual_account_configuration_ready=eir_accrual_account_configuration_ready,
                            eir_accrual_account_configuration_blocker=eir_accrual_account_configuration_blocker,
                        )

                    measurement = self._load_measurement(
                        cursor,
                        loan_id=loan_id,
                        cutover_date=cutover_date,
                    )

                events = self._load_source_events(
                    cursor,
                    loan_id=loan_id,
                    cutover_date=cutover_date,
                )
                fiscal_periods = self._load_fiscal_periods(
                    cursor,
                    cutover_date=cutover_date,
                )

        if len(events) > MAX_SOURCE_EVENTS:
            return self._blocked_pack(
                loan_id=loan_id,
                loan=loan,
                cutover_date=cutover_date,
                opening_balance_prepared=opening_balance_prepared,
                opening_balance_posted=opening_balance_posted,
                opening_balance_entry_number=opening_balance_entry_number,
                blocker_code="source_history_too_large",
                blocker_message="More than 5,000 post-cutover source events exist for this loan. Allocation is blocked rather than silently truncating history.",
                source_event_count=len(events),
                protected_snapshot_available=protected_snapshot_available,
                protected_snapshot_reconciled=protected_snapshot_reconciled,
                protected_snapshot_blocker=protected_snapshot_blocker,
                account_configuration_ready=account_configuration_ready,
                account_configuration_blocker=account_configuration_blocker,
                eir_accrual_account_configuration_ready=eir_accrual_account_configuration_ready,
                eir_accrual_account_configuration_blocker=eir_accrual_account_configuration_blocker,
            )

        state = EirCutoverState(
            loan_id=loan_id,
            calculation_mode=str(measurement["calculation_mode"] or ""),
            cutover_date=cutover_date,
            due_date=measurement["due_date"],
            measurement_status=str(measurement["measurement_status"] or ""),
            daily_eir=(
                Decimal(measurement["daily_eir"])
                if measurement["daily_eir"] is not None
                else None
            ),
            loan_component=(
                Decimal(measurement["loan_component"])
                if measurement["loan_component"] is not None
                else None
            ),
            accrued_interest_component=(
                Decimal(measurement["accrued_interest_component"])
                if measurement["accrued_interest_component"] is not None
                else None
            ),
            gross_carrying_amount=(
                Decimal(measurement["gross_carrying_amount"])
                if measurement["gross_carrying_amount"] is not None
                else None
            ),
        )
        source_events = tuple(
            EirCashSourceEvent(
                transaction_id=UUID(str(row["transaction_id"])),
                collection_date=row["collection_date"],
                accepted_at=row["accepted_at"],
                entry_type=str(row["entry_type"]),
                amount=Decimal(row["amount"] or 0),
                is_voided=bool(row["is_voided"]),
            )
            for row in events
        )
        allocation = allocate_event_date_eir_cash(state, source_events)
        event_state = {
            UUID(str(row["transaction_id"])): row
            for row in events
        }
        collection_journal_previews = tuple(
            build_regular_collection_journal_preview(
                item,
                allocation_result_status=allocation.status,
                opening_balance_posted=opening_balance_posted,
                protected_snapshot_available=protected_snapshot_available,
                protected_snapshot_reconciled=protected_snapshot_reconciled,
                source_history_complete=True,
                account_configuration_ready=account_configuration_ready,
                account_configuration_blocker=account_configuration_blocker,
                is_voided=bool(event_state[item.transaction_id]["is_voided"]),
                existing_journal_status=(
                    str(event_state[item.transaction_id]["journal_status"])
                    if event_state[item.transaction_id]["journal_status"]
                    else None
                ),
                reversal_status=(
                    str(event_state[item.transaction_id]["reversal_status"])
                    if event_state[item.transaction_id]["reversal_status"]
                    else None
                ),
            )
            for item in allocation.allocations
        )
        eir_accrual_previews: list[RegularEirAccrualJournalPreview] = []
        prior_accrual_boundary = cutover_date
        for item in allocation.allocations:
            row = event_state[item.transaction_id]
            eir_accrual_previews.append(
                build_regular_eir_accrual_journal_preview(
                    item,
                    allocation_result_status=allocation.status,
                    accrual_start_date=prior_accrual_boundary,
                    fiscal_periods=fiscal_periods,
                    opening_balance_posted=opening_balance_posted,
                    protected_snapshot_available=protected_snapshot_available,
                    protected_snapshot_reconciled=protected_snapshot_reconciled,
                    source_history_complete=True,
                    account_configuration_ready=eir_accrual_account_configuration_ready,
                    account_configuration_blocker=eir_accrual_account_configuration_blocker,
                    is_voided=bool(row["is_voided"]),
                    existing_accrual_journal_status=(
                        str(row["accrual_journal_status"])
                        if row["accrual_journal_status"]
                        else None
                    ),
                    accrual_reversal_status=(
                        str(row["accrual_reversal_status"])
                        if row["accrual_reversal_status"]
                        else None
                    ),
                    collection_journal_status=(
                        str(row["journal_status"])
                        if row["journal_status"]
                        else None
                    ),
                )
            )
            prior_accrual_boundary = item.collection_date
        return EirCashAllocationPack(
            loan_id=loan_id,
            loan_number=str(loan["loan_number"]),
            client_name=str(loan["client_name"]),
            cutover_date=cutover_date,
            opening_balance_prepared=opening_balance_prepared,
            opening_balance_posted=opening_balance_posted,
            opening_balance_entry_number=opening_balance_entry_number,
            source_event_count=len(source_events),
            source_history_complete=True,
            blocker_code=None,
            blocker_message=None,
            allocation=allocation,
            protected_snapshot_available=protected_snapshot_available,
            protected_snapshot_reconciled=protected_snapshot_reconciled,
            protected_snapshot_blocker=protected_snapshot_blocker,
            account_configuration_ready=account_configuration_ready,
            account_configuration_blocker=account_configuration_blocker,
            eir_accrual_account_configuration_ready=eir_accrual_account_configuration_ready,
            eir_accrual_account_configuration_blocker=eir_accrual_account_configuration_blocker,
            eir_accrual_previews=tuple(eir_accrual_previews),
            collection_journal_previews=collection_journal_previews,
        )

    @staticmethod
    def _blocked_pack(
        *,
        loan_id: UUID,
        loan,
        cutover_date: date | None,
        opening_balance_prepared: bool,
        opening_balance_posted: bool,
        opening_balance_entry_number: str | None,
        blocker_code: str,
        blocker_message: str,
        source_event_count: int = 0,
        protected_snapshot_available: bool = False,
        protected_snapshot_reconciled: bool = False,
        protected_snapshot_blocker: str | None = None,
        account_configuration_ready: bool,
        account_configuration_blocker: str | None,
        eir_accrual_account_configuration_ready: bool,
        eir_accrual_account_configuration_blocker: str | None,
    ) -> EirCashAllocationPack:
        return EirCashAllocationPack(
            loan_id=loan_id,
            loan_number=str(loan["loan_number"]),
            client_name=str(loan["client_name"]),
            cutover_date=cutover_date,
            opening_balance_prepared=opening_balance_prepared,
            opening_balance_posted=opening_balance_posted,
            opening_balance_entry_number=opening_balance_entry_number,
            source_event_count=source_event_count,
            source_history_complete=(
                blocker_code not in {
                    "source_history_too_large",
                    "protected_cutover_snapshot_required",
                    "protected_cutover_snapshot_not_reconciled",
                }
            ),
            blocker_code=blocker_code,
            blocker_message=blocker_message,
            allocation=None,
            protected_snapshot_available=protected_snapshot_available,
            protected_snapshot_reconciled=protected_snapshot_reconciled,
            protected_snapshot_blocker=protected_snapshot_blocker,
            account_configuration_ready=account_configuration_ready,
            account_configuration_blocker=account_configuration_blocker,
            eir_accrual_account_configuration_ready=eir_accrual_account_configuration_ready,
            eir_accrual_account_configuration_blocker=eir_accrual_account_configuration_blocker,
        )

    @staticmethod
    def _account_configuration(
        cursor,
        *,
        required_keys: tuple[str, ...],
        label: str,
    ) -> tuple[bool, str | None]:
        cursor.execute(
            """
            select system_key, is_active, is_posting
            from accounting.accounts
            where system_key = any(%s)
            """,
            (list(required_keys),),
        )
        rows = {str(row["system_key"]): row for row in cursor.fetchall()}
        missing = [
            key for key in required_keys
            if key not in rows
        ]
        invalid = [
            key
            for key, row in rows.items()
            if not bool(row["is_active"]) or not bool(row["is_posting"])
        ]
        if missing:
            return (
                False,
                f"Missing required {label} account mapping: "
                + ", ".join(missing),
            )
        if invalid:
            return (
                False,
                f"Required {label} accounts are inactive or non-posting: "
                + ", ".join(invalid),
            )
        return True, None

    @staticmethod
    def _load_current_cutover(cursor):
        cursor.execute(
            """
            select
                workbook.id as workbook_id,
                workbook.cutover_date,
                (prep.workbook_id is not null) as opening_balance_prepared,
                (posting.workbook_id is not null) as opening_balance_posted,
                posting.entry_number as opening_balance_entry_number
            from accounting.opening_balance_workbooks workbook
            left join accounting.opening_balance_journal_preparations prep
              on prep.workbook_id = workbook.id
            left join accounting.opening_balance_journal_postings posting
              on posting.workbook_id = workbook.id
            order by workbook.created_at desc
            limit 1
            """
        )
        return cursor.fetchone()

    @staticmethod
    def _load_measurement(cursor, *, loan_id: UUID, cutover_date):
        cursor.execute(
            """
            select *
            from accounting.measure_loan_at_cutover(%s, %s)
            """,
            (loan_id, cutover_date),
        )
        row = cursor.fetchone()
        if row is None:
            raise EirCashAllocationLoanNotFound("Loan measurement source was not found.")
        return row

    @staticmethod
    def _load_protected_snapshot(cursor, *, workbook_id: UUID, loan_id: UUID):
        cursor.execute(
            """
            select
                snapshot.calculation_mode,
                snapshot.cutover_date,
                snapshot.due_date,
                snapshot.measurement_status,
                snapshot.daily_eir,
                snapshot.loan_component,
                snapshot.accrued_interest_component,
                snapshot.gross_carrying_amount,
                snapshot.measurement_policy_version
            from accounting.opening_balance_loan_measurement_snapshots snapshot
            where snapshot.workbook_id = %s
              and snapshot.loan_id = %s
            """,
            (workbook_id, loan_id),
        )
        return cursor.fetchone()

    @staticmethod
    def _load_snapshot_reconciliation(cursor, *, workbook_id: UUID):
        cursor.execute(
            """
            select
                measurement_policy_version,
                ledger_anchor_ready,
                ledger_anchor_blocker
            from accounting.opening_balance_loan_snapshot_reconciliation
            where workbook_id = %s
            """,
            (workbook_id,),
        )
        return cursor.fetchone()

    @staticmethod
    def _load_source_events(cursor, *, loan_id: UUID, cutover_date):
        cursor.execute(
            """
            select
                t.id as transaction_id,
                t.collection_date,
                t.accepted_at,
                t.entry_type,
                t.amount,
                t.is_voided,
                journal.status as journal_status,
                reversal.status as reversal_status,
                accrual_journal.status as accrual_journal_status,
                accrual_reversal.status as accrual_reversal_status
            from lending.collection_transactions t
            left join accounting.journal_entries journal
              on journal.source_event_key = 'collection:' || t.id::text
            left join accounting.journal_entries reversal
              on reversal.reversal_of_entry_id = journal.id
            left join accounting.journal_entries accrual_journal
              on accrual_journal.source_event_key =
                 'eir_accrual:collection:' || t.id::text
            left join accounting.journal_entries accrual_reversal
              on accrual_reversal.reversal_of_entry_id = accrual_journal.id
            where t.loan_id = %s
              and t.collection_date > %s
            order by t.collection_date, t.accepted_at, t.id
            limit %s
            """,
            (loan_id, cutover_date, MAX_SOURCE_EVENTS + 1),
        )
        return tuple(cursor.fetchall())

    @staticmethod
    def _load_fiscal_periods(
        cursor,
        *,
        cutover_date: date,
    ) -> tuple[AccountingFiscalPeriodReference, ...]:
        cursor.execute(
            """
            select id, label, start_date, end_date, status
            from accounting.fiscal_periods
            where end_date > %s
            order by start_date, end_date, id
            """,
            (cutover_date,),
        )
        return tuple(
            AccountingFiscalPeriodReference(
                period_id=UUID(str(row["id"])),
                label=str(row["label"]),
                start_date=row["start_date"],
                end_date=row["end_date"],
                status=str(row["status"]),
            )
            for row in cursor.fetchall()
        )
