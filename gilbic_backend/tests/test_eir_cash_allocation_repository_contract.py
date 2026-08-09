from __future__ import annotations

import inspect

from gilbic_backend.eir_cash_allocation_repository import (
    MAX_SOURCE_EVENTS,
    PROTECTED_MEASUREMENT_POLICY_VERSION,
    PostgresEirCashAllocationRepository,
)


def test_repository_uses_current_cutover_and_protected_snapshot_after_preparation() -> None:
    source = inspect.getsource(PostgresEirCashAllocationRepository)

    assert "order by workbook.created_at desc" in source
    assert "if opening_balance_prepared" in source
    assert "accounting.opening_balance_loan_measurement_snapshots" in source
    assert "accounting.opening_balance_loan_snapshot_reconciliation" in source
    assert "protected_cutover_snapshot_required" in source
    assert "protected_cutover_snapshot_not_reconciled" in source
    assert "ledger_anchor_ready" in source
    assert "accounting.measure_loan_at_cutover" in source
    assert source.index("if opening_balance_prepared") < source.index(
        "measurement = self._load_measurement"
    )
    assert PROTECTED_MEASUREMENT_POLICY_VERSION == "eir_cutover_v1"


def test_repository_keeps_dynamic_preview_and_complete_post_cutover_source_history() -> None:
    source = inspect.getsource(PostgresEirCashAllocationRepository)

    assert "same_day_cash_count" in source
    assert "t.collection_date > %s" in source
    assert "order by t.collection_date, t.accepted_at, t.id" in source
    assert "MAX_SOURCE_EVENTS + 1" in source
    assert MAX_SOURCE_EVENTS == 5000


def test_repository_fail_closes_collection_proposals_against_accounts_and_journal_state() -> None:
    source = inspect.getsource(PostgresEirCashAllocationRepository)

    assert "REGULAR_COLLECTION_ACCOUNT_KEYS" in source
    assert "build_regular_collection_journal_preview" in source
    assert "from accounting.accounts" in source
    assert "left join accounting.journal_entries journal" in source
    assert "left join accounting.journal_entries reversal" in source
    assert "journal.status as journal_status" in source
    assert "reversal.status as reversal_status" in source


def test_repository_contains_no_accounting_or_lending_write_statement() -> None:
    source = inspect.getsource(PostgresEirCashAllocationRepository).lower()

    forbidden = (
        "insert into accounting.",
        "update accounting.",
        "delete from accounting.",
        "insert into lending.",
        "update lending.",
        "delete from lending.",
        "post_journal_entry",
    )
    for phrase in forbidden:
        assert phrase not in source
