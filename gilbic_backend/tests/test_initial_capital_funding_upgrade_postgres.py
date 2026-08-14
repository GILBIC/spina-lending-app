from __future__ import annotations

import importlib.util
from pathlib import Path

import psycopg


TEST_DIR = Path(__file__).resolve().parent
SOURCE_PATH = TEST_DIR / "test_initial_capital_funding_postgres.py"
_spec = importlib.util.spec_from_file_location("initial_capital_funding_cases", SOURCE_PATH)
assert _spec is not None and _spec.loader is not None
cases = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cases)

SQL_0081 = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0081_add_protected_initial_capital_funding.sql"
).read_text(encoding="utf-8")


def _install_0081_on_current_schema(connection: psycopg.Connection) -> None:
    assert connection.execute(
        "SELECT to_regprocedure('accounting.create_manual_journal_draft(date,text,uuid,jsonb)') IS NOT NULL"
    ).fetchone()[0]
    assert connection.execute(
        "SELECT to_regclass('accounting.ecl_accounting_writeoffs') IS NOT NULL"
    ).fetchone()[0]
    assert connection.execute(
        "SELECT to_regclass('accounting.initial_capital_funding_evidence') IS NULL"
    ).fetchone()[0]
    connection.execute(cases._body(SQL_0081))


def _run_case(case) -> None:
    original = cases._install
    cases._install = _install_0081_on_current_schema
    try:
        case()
    finally:
        cases._install = original


def test_a6_initial_capital_full_schema_lifecycle_and_retry() -> None:
    _run_case(cases.test_initial_capital_funding_protected_general_journal_lifecycle_and_retry)


def test_a6_initial_capital_full_schema_atomic_rollback() -> None:
    _run_case(cases.test_initial_capital_funding_posting_is_atomic_on_forced_audit_failure)
