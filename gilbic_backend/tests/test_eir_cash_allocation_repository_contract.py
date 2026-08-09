from __future__ import annotations

import inspect

from gilbic_backend.eir_cash_allocation_repository import (
    MAX_SOURCE_EVENTS,
    PostgresEirCashAllocationRepository,
)


def test_repository_uses_current_cutover_and_reconciled_measurement_source() -> None:
    source = inspect.getsource(PostgresEirCashAllocationRepository)

    assert "order by workbook.created_at desc" in source
    assert "accounting.measure_loan_at_cutover" in source
    assert "same_day_cash_count" in source
    assert "t.collection_date > %s" in source
    assert "order by t.collection_date, t.accepted_at, t.id" in source
    assert "MAX_SOURCE_EVENTS + 1" in source
    assert MAX_SOURCE_EVENTS == 5000


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
