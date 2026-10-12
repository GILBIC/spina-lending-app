"""One close inventory must agree with every supported source admission gate."""

from pathlib import Path

import psycopg
import pytest
from psycopg.rows import dict_row
from test_accounting_book_postgres import book_db as _book_db
from test_financial_statement_snapshot_postgres import (
    isolated_statement_database as _isolated_statement_database,
)
from test_legacy_source_completeness_postgres import _collection
from test_legacy_source_completeness_postgres import legacy_close as _legacy_close
from test_liability_control_postgres import liabilities as _liabilities
from test_liability_control_postgres import line, movement, register
from test_period_close_postgres import _body, _move_to_review
from test_treasury_receipt_accounting_postgres import (
    install,
    mapping,
    post,
    prepare,
    seed,
)
from test_treasury_receipt_accounting_postgres import receipt_db as _receipt_db

from gilbic_backend import period_close_repository

SQL_ROOT = Path(__file__).resolve().parents[1] / "sql"
COMPOSITION = SQL_ROOT / "0148_compose_accounting_source_controls.sql"
book_db = _book_db
liabilities = _liabilities
receipt_db = _receipt_db
legacy_close = _legacy_close
isolated_statement_database = _isolated_statement_database


def compose(conn):
    for name in (
        "0141_add_accounting_source_close_guard.sql",
        "0145_add_treasury_receipt_accounting.sql",
        "0146_add_legacy_source_completeness.sql",
        "0147_add_liability_control_schedule.sql",
    ):
        install(conn, SQL_ROOT / name)
    if COMPOSITION.exists():
        install(conn, COMPOSITION)


def test_exact_receipt_cash_clears_public_inventory_and_review(receipt_db):
    f = receipt_db
    compose(f["conn"])
    query = "SELECT count(*) AS count FROM accounting.period_source_blockers(%s)"
    assert f["conn"].execute(query, (f["period"],)).fetchone()["count"] == 1
    post(f, prepare(f, mapping(f)))
    assert f["conn"].execute(query, (f["period"],)).fetchone()["count"] == 0
    f["conn"].execute(
        "SELECT accounting.assert_period_source_complete(%s)", (f["period"],)
    )
    assert (
        f["conn"]
        .execute(
            "SELECT accounting.set_fiscal_period_status(%s,'review',%s) AS status",
            (f["period"], f["actor"].user_id),
        )
        .fetchone()["status"]
        == "review"
    )


def test_unregistered_net_zero_liability_lines_still_block(liabilities):
    f = liabilities
    compose(f["conn"])
    line(f)
    line(f, debit=True)
    period = (
        f["conn"]
        .execute(
            "SELECT id FROM accounting.fiscal_periods WHERE start_date=%s", (f["day"],)
        )
        .fetchone()[0]
    )
    rows = (
        f["conn"]
        .execute(
            "SELECT source_type,reason FROM accounting.period_source_blockers(%s)",
            (period,),
        )
        .fetchall()
    )
    assert ("liability_control", "liability_lines_unregistered") in rows
    with pytest.raises(psycopg.Error, match="unreconciled"), f["conn"].transaction():
        _move_to_review(f["conn"], period, f["actor"])


def test_matched_partial_payable_keeps_balance_and_can_review(liabilities):
    f = liabilities
    compose(f["conn"])
    obligation = register(f, line(f))
    movement(f, obligation, line(f, "40.00", debit=True))
    period = (
        f["conn"]
        .execute(
            "SELECT id FROM accounting.fiscal_periods WHERE start_date=%s", (f["day"],)
        )
        .fetchone()[0]
    )
    assert (
        f["conn"]
        .execute(
            "SELECT count(*) FROM accounting.period_source_blockers(%s)", (period,)
        )
        .fetchone()[0]
        == 0
    )
    _move_to_review(f["conn"], period, f["actor"])
    assert (
        f["conn"]
        .execute(
            "SELECT outstanding_amount FROM accounting.liability_control_schedule(%s) WHERE obligation_id=%s",
            (f["day"], obligation),
        )
        .fetchone()[0]
        == 60
    )


def test_legacy_source_appears_in_same_public_inventory(legacy_close):
    f = legacy_close
    f["conn"].execute(
        _body(
            (SQL_ROOT / "0144_add_accounting_book_identity.sql").read_text(
                encoding="utf-8"
            )
        )
    )
    compose(f["conn"])
    collection = _collection(f)
    rows = (
        f["conn"]
        .execute(
            "SELECT source_id FROM accounting.period_source_blockers(%s)",
            (f["period"],),
        )
        .fetchall()
    )
    assert (collection,) in rows
    state = (
        f["conn"]
        .execute(
            "SELECT blocker_count FROM accounting.period_source_close_state WHERE fiscal_period_id=%s",
            (f["period"],),
        )
        .fetchone()[0]
    )
    assert state == len(rows)


def test_composed_repository_includes_accounting_evidence_and_scoped_families(
    isolated_statement_database, monkeypatch
):
    url = isolated_statement_database
    with psycopg.connect(url, row_factory=dict_row) as conn:
        f = seed(conn)
        compose(conn)
        post(f, prepare(f, mapping(f)))
        # The posted cash receipt is complete; an unrelated payable lacks its
        # counterparty schedule and must remain visible under accounting access.
        conn.row_factory = psycopg.rows.tuple_row
        line(f | {"actor": f["actor"].user_id})
    monkeypatch.setattr(
        period_close_repository, "open_connection", lambda: psycopg.connect(url)
    )
    result = period_close_repository.PostgresPeriodCloseRepository().source_coverage(
        f["period"], actor=f["actor"]
    )
    assert result["source_families"] == [
        "treasury",
        "collector",
        "lending",
        "tax",
        "period_assessment",
        "liabilities",
    ]
    assert result["blocker_count"] == 1
    assert result["blockers"][0]["source_type"] == "liability_control"
    assert result["blockers"][0]["amount"] == "100.00"
