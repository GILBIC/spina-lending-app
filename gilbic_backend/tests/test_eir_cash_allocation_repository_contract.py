from __future__ import annotations

import ast
import inspect
from uuid import UUID

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
    assert "REGULAR_EIR_ACCRUAL_ACCOUNT_KEYS" in source
    assert "build_regular_eir_accrual_journal_preview" in source
    assert "build_regular_accounting_sequence_preview" in source
    assert "accounting_sequence_previews" in source
    assert "zip(" in source
    assert "strict=True" in source
    assert "from accounting.fiscal_periods" in source
    assert "'eir_accrual:collection:' || t.id::text" in source
    assert "accrual_journal.status as accrual_journal_status" in source
    assert "accrual_reversal.status as accrual_reversal_status" in source


def test_repository_preserves_account_configuration_on_every_blocked_response() -> None:
    source = inspect.getsource(PostgresEirCashAllocationRepository)
    tree = ast.parse(source)
    blocked_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "_blocked_pack"
    ]

    assert blocked_calls
    for call in blocked_calls:
        keyword_names = {keyword.arg for keyword in call.keywords}
        assert "account_configuration_ready" in keyword_names
        assert "account_configuration_blocker" in keyword_names
        assert "eir_accrual_account_configuration_ready" in keyword_names
        assert "eir_accrual_account_configuration_blocker" in keyword_names

    loan_id = UUID("00000000-0000-0000-0000-000000000001")
    loan = {"loan_number": "REG-1", "client_name": "Test Client"}
    ready_pack = PostgresEirCashAllocationRepository._blocked_pack(
        loan_id=loan_id,
        loan=loan,
        cutover_date=None,
        opening_balance_prepared=False,
        opening_balance_posted=False,
        opening_balance_entry_number=None,
        blocker_code="cutover_required",
        blocker_message="Cutover is required.",
        account_configuration_ready=True,
        account_configuration_blocker=None,
        eir_accrual_account_configuration_ready=True,
        eir_accrual_account_configuration_blocker=None,
    )
    account_blocker = "Missing required Regular collection account mapping: loans_receivable_regular"
    blocked_pack = PostgresEirCashAllocationRepository._blocked_pack(
        loan_id=loan_id,
        loan=loan,
        cutover_date=None,
        opening_balance_prepared=False,
        opening_balance_posted=False,
        opening_balance_entry_number=None,
        blocker_code="cutover_required",
        blocker_message="Cutover is required.",
        account_configuration_ready=False,
        account_configuration_blocker=account_blocker,
        eir_accrual_account_configuration_ready=False,
        eir_accrual_account_configuration_blocker="Missing required Regular EIR accrual account mapping: interest_income_regular",
    )

    assert ready_pack.account_configuration_ready is True
    assert ready_pack.account_configuration_blocker is None
    assert blocked_pack.account_configuration_ready is False
    assert blocked_pack.account_configuration_blocker == account_blocker
    assert ready_pack.eir_accrual_account_configuration_ready is True
    assert ready_pack.eir_accrual_account_configuration_blocker is None
    assert blocked_pack.eir_accrual_account_configuration_ready is False
    assert "interest_income_regular" in (
        blocked_pack.eir_accrual_account_configuration_blocker or ""
    )


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
