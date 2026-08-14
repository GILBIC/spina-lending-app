from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)

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


def test_a6_initial_capital_full_schema_manual_reversal_is_rejected() -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        try:
            _install_0081_on_current_schema(connection)
            suffix = "V" + uuid4().hex[:9]
            actor_id = cases._management_actor(connection, suffix)
            period_id, today = cases._period(connection, suffix)
            evidence_id = cases._record(
                connection,
                actor_id=actor_id,
                key=uuid4(),
                funding_date=today,
                amount="50000.00",
                cash_code="1030",
                suffix=suffix,
                digest_char="f",
            )
            journal_id = connection.execute(
                "SELECT accounting.prepare_initial_capital_funding_journal(%s,%s)",
                (evidence_id, actor_id),
            ).fetchone()[0]
            cases._post(
                connection,
                evidence_id=evidence_id,
                actor_id=actor_id,
                token="9" * 64,
                digest="f" * 64,
                amount="50000.00",
                cash_code="1030",
                posting_date=today,
                period_id=period_id,
            )

            with pytest.raises(
                psycopg.Error,
                match="cannot be reversed through the manual General Journal",
            ):
                with connection.transaction():
                    connection.execute(
                        "SELECT accounting.create_manual_reversal_draft(%s,%s,%s,%s)",
                        (
                            journal_id,
                            actor_id,
                            today,
                            "Unauthorized manual reversal of protected initial capital",
                        ),
                    )

            assert connection.execute(
                "SELECT count(*) FROM accounting.journal_entries WHERE reversal_of_entry_id=%s",
                (journal_id,),
            ).fetchone()[0] == 0
        finally:
            connection.rollback()
