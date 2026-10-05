"""Cash, equity, comparative figures and formal close share one posted ledger."""

from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from gilbic_backend.financial_statements_api import _pack_payload
from psycopg.types.json import Jsonb
from test_accounting_book_postgres import configure
from test_financial_statement_snapshot_postgres import (
    isolated_statement_database as _isolated_statement_database,
)
from test_period_close_postgres import (
    _body,
    _management_actor,
    _manual_journal,
    _move_to_review,
    _period,
    _post_close,
)
from test_reporting_policy_postgres import policy

from gilbic_backend import financial_statements_repository as repository

isolated_statement_database = _isolated_statement_database


@pytest.mark.parametrize(("income", "expense"), [(100, 40), (0, 40), (0, 0)])
def test_report_components_reconcile_before_and_after_close(
    isolated_statement_database, monkeypatch, income, expense
):
    url = isolated_statement_database
    with psycopg.connect(url) as conn:
        for name in (
            "0140_add_accounting_book_identity.sql",
            "0144_add_liability_control_schedule.sql",
            "0147_add_reporting_evidence.sql",
        ):
            conn.execute(
                _body(
                    (Path(__file__).resolve().parents[1] / "sql" / name).read_text(
                        encoding="utf-8"
                    )
                )
            )
        actor = _management_actor(conn, uuid4().hex)
        book = configure(conn, actor, "owner_operations")
        period, start, end = _period(conn, actor_id=actor, suffix=uuid4().hex)
        f = {"conn": conn, "book": book, "actor": actor, "period": period, "day": start}
        selected = policy(f)
        for account, amount, category, payment in (
            ("3000", 200, "financing", False),
            ("4000", income, "operating", False),
            ("5200", expense, "operating", True),
        ):
            if amount == 0:
                continue
            journal, _ = _manual_journal(
                conn,
                actor_id=actor,
                posting_date=start,
                description="Synthetic cash flow",
                lines=[
                    {
                        "account_code": "1010",
                        "debit": "0" if payment else str(amount),
                        "credit": str(amount) if payment else "0",
                    },
                    {
                        "account_code": account,
                        "debit": str(amount) if payment else "0",
                        "credit": "0" if payment else str(amount),
                    },
                ],
            )
            cash_line = conn.execute(
                "SELECT id FROM accounting.journal_lines WHERE journal_entry_id=%s AND line_number=1",
                (journal,),
            ).fetchone()[0]
            exact = format(Decimal(-amount if payment else amount), ".2f")
            payload = {
                "journal_line_id": str(cash_line),
                "expected_amount": exact,
                "expected_version": 0,
                "allocations": [{"category": category, "amount": exact}],
                "evidence_reference": "test:retained-classification",
                "evidence_digest": "c" * 64,
                "reviewed": True,
            }
            conn.execute(
                "SELECT accounting.retain_cash_flow_classification(%s,%s,%s,%s,%s)",
                (uuid4(), book, selected, Jsonb(payload), actor),
            )
    monkeypatch.setattr(repository, "open_connection", lambda: psycopg.connect(url))
    reports = repository.PostgresFinancialStatementsRepository()
    before = _pack_payload(reports.load_statement_pack(period_id=period))
    total = format(Decimal(200 + income - expense), ".2f")
    assert (
        before["reporting_supplement"]["changes_in_equity"]["closing_equity"] == total
    )
    assert before["reporting_supplement"]["changes_in_equity"]["reconciled"] is True
    assert before["reporting_supplement"]["cash_flows"]["closing_cash"] == total
    assert before["reporting_supplement"]["cash_flows"]["reconciled"] is True
    with psycopg.connect(url) as conn:
        _move_to_review(conn, period, actor)
        prepared = conn.execute(
            "SELECT accounting.prepare_period_close(%s,%s)", (period, actor)
        ).fetchone()[0]
        row = conn.execute(
            "SELECT close_digest,net_income FROM accounting.period_close_preparations WHERE id=%s",
            (prepared,),
        ).fetchone()
        _post_close(
            conn,
            period_id=period,
            actor_id=actor,
            token="d" * 64,
            close_digest=row[0],
            net_income=str(row[1]),
            end_date=end,
        )
    after = _pack_payload(reports.load_statement_pack(period_id=period))
    assert (
        after["reporting_supplement"]["changes_in_equity"]
        == before["reporting_supplement"]["changes_in_equity"]
    )
    assert after["profit_or_loss"] == before["profit_or_loss"]
    assert after["reporting_supplement"]["cash_flows"]["net_cash_flow"] == total
    with psycopg.connect(url) as conn:
        next_period = conn.execute(
            "SELECT accounting.create_fiscal_period(%s,%s,%s,%s)",
            (uuid4().hex, end + timedelta(days=1), end + timedelta(days=5), actor),
        ).fetchone()[0]
    next_report = _pack_payload(reports.load_statement_pack(period_id=next_period))
    assert (
        next_report["reporting_supplement"]["changes_in_equity"]["opening_equity"]
        == total
    )
    comparative = next_report["reporting_supplement"]["comparative"]
    assert comparative["period"]["period_id"] == str(period)
    assert comparative["profit_or_loss"] == after["profit_or_loss"]
    assert comparative["reporting_supplement"]["cash_flows"]["reconciled"] is True


def test_protected_opening_reversal_never_becomes_a_financing_payment(
    isolated_statement_database, monkeypatch
):
    url = isolated_statement_database
    with psycopg.connect(url) as conn:
        conn.execute(
            _body(
                (
                    Path(__file__).resolve().parents[1]
                    / "sql/0147_add_reporting_evidence.sql"
                ).read_text(encoding="utf-8")
            )
        )
        actor = _management_actor(conn, uuid4().hex)
        book = configure(conn, actor, "owner_operations")
        period, start, _ = _period(conn, actor_id=actor, suffix=uuid4().hex)
        selected = policy(
            {"conn": conn, "book": book, "actor": actor, "period": period}
        )
        conn.execute("SELECT set_config('accounting.cutover_write_allowed','on',true)")
        workbook = conn.execute(
            """INSERT INTO accounting.opening_balance_workbooks
            (cutover_date,status,profit_loss_policy_confirmed,profit_loss_policy_note,created_by_user_id,updated_by_user_id)
            VALUES(%s,'review_ready',true,'Synthetic reporting test',%s,%s) RETURNING id""",
            (start, actor, actor),
        ).fetchone()[0]
        conn.execute(
            """INSERT INTO accounting.opening_balance_workbook_lines
            (workbook_id,account_id,source_reference_amount,source_basis,requirement_type,guidance,
             proposed_debit,proposed_credit,verification_status,evidence_note,updated_by_user_id)
            SELECT %s,id,100,'synthetic_test','manual_required','Synthetic reporting test',
              CASE WHEN code='1010' THEN 100 ELSE 0 END,CASE WHEN code='3000' THEN 100 ELSE 0 END,
              'verified','Synthetic evidence',%s FROM accounting.accounts WHERE code IN ('1010','3000')""",
            (workbook, actor),
        )
        original = conn.execute(
            "SELECT accounting.create_opening_balance_journal_draft(%s,%s)",
            (workbook, actor),
        ).fetchone()[0]
        conn.execute(
            "SELECT accounting.post_opening_balance_journal(%s,%s)", (workbook, actor)
        )
        reversal = conn.execute(
            "SELECT accounting.create_manual_reversal_draft(%s,%s,%s,%s)",
            (original, actor, start, "Synthetic opening reversal"),
        ).fetchone()[0]
        conn.execute(
            "SELECT accounting.post_manual_journal_entry(%s,%s)", (reversal, actor)
        )
        cash_line = conn.execute(
            "SELECT line.id FROM accounting.journal_lines line JOIN accounting.accounts a ON a.id=line.account_id WHERE line.journal_entry_id=%s AND a.code='1010'",
            (reversal,),
        ).fetchone()[0]
        payload = {
            "journal_line_id": str(cash_line),
            "expected_amount": "-100.00",
            "expected_version": 0,
            "allocations": [{"category": "financing", "amount": "-100.00"}],
            "evidence_reference": "test:opening-reversal",
            "evidence_digest": "b" * 64,
            "reviewed": True,
        }
        with (
            pytest.raises(psycopg.Error, match="original posted cash"),
            conn.transaction(),
        ):
            conn.execute(
                "SELECT accounting.retain_cash_flow_classification(%s,%s,%s,%s,%s)",
                (uuid4(), book, selected, Jsonb(payload), actor),
            )
    monkeypatch.setattr(repository, "open_connection", lambda: psycopg.connect(url))
    report = _pack_payload(
        repository.PostgresFinancialStatementsRepository().load_statement_pack(
            period_id=period
        )
    )
    cash = report["reporting_supplement"]["cash_flows"]
    assert cash["reconciled"] is True
    assert cash["net_cash_flow"] == "0.00"
    assert cash["categories"]["financing"]["payments"] == "0.00"
    assert len(cash["cash_lines"]) == 2
    assert all(row["is_opening_adjustment"] for row in cash["cash_lines"])
