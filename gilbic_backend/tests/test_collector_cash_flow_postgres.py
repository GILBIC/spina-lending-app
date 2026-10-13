"""Actual Collector cash proof prevents double-counted statement receipts."""

from uuid import UUID, uuid4

import psycopg
import pytest
from collector_accounting_test_support import accepted, post, prepare, source_case
from psycopg.rows import dict_row, tuple_row
from psycopg.types.json import Jsonb
from test_financial_statement_snapshot_postgres import (
    isolated_statement_database as _isolated_statement_database,
)
from test_reporting_policy_postgres import policy

from gilbic_backend import financial_statements_repository as reports

isolated_statement_database = _isolated_statement_database


@pytest.mark.parametrize(
    "case", ["valid", "gross_operating", "gross_mixed", "correction"]
)
def test_actual_collector_settlement_reports_only_original_collection_and_excess(
    isolated_statement_database, monkeypatch, tmp_path, case
):
    url = isolated_statement_database
    with psycopg.connect(url, row_factory=dict_row) as conn:
        f = source_case(conn, tmp_path, monkeypatch)
        acceptance = accepted(f)
        native = post(f, prepare(f, "settlement", UUID(acceptance["settlement"]["id"])))
        conn.row_factory = tuple_row
        selected = policy(f | {"actor": f["actor"].user_id})
        conn.row_factory = dict_row
        lines = conn.execute(
            "SELECT l.id,l.journal_entry_id,a.code,l.debit-l.credit AS amount "
            "FROM accounting.journal_lines l JOIN accounting.accounts a ON a.id=l.account_id "
            "JOIN accounting.journal_entries j ON j.id=l.journal_entry_id "
            "WHERE j.status='posted' AND j.fiscal_period_id=%s AND a.code IN('1010','1020','1030')",
            (f["period"],),
        ).fetchall()
        assert len(lines) == 3
        for line in lines:
            allocations = [
                {"category": "operating", "amount": format(line["amount"], ".2f")}
            ]
            if line["journal_entry_id"] == native:
                if case == "valid" and line["code"] == "1020":
                    allocations = [{"category": "internal", "amount": "-100.00"}]
                elif case == "valid":
                    allocations = [
                        {"category": "internal", "amount": "100.00"},
                        {"category": "operating", "amount": "10.00"},
                    ]
                elif case == "gross_mixed" and line["code"] == "1010":
                    allocations[0]["category"] = "financing"
            conn.execute(
                "SELECT accounting.retain_cash_flow_classification(%s,%s,%s,%s,%s)",
                (
                    uuid4(),
                    f["book"],
                    selected,
                    Jsonb(
                        {
                            "journal_line_id": str(line["id"]),
                            "expected_amount": format(line["amount"], ".2f"),
                            "expected_version": 0,
                            "allocations": allocations,
                            "evidence_reference": "test:collector-statement",
                            "evidence_digest": "a" * 64,
                            "reviewed": True,
                        }
                    ),
                    f["actor"].user_id,
                ),
            )
        if case == "correction":
            conn.execute(
                "INSERT INTO treasury.event_revisions(id,event_id,version,action,reason,actor_id) "
                "VALUES(%s,%s,2,'correct','Synthetic changed count observation',%s)",
                (
                    uuid4(),
                    UUID(acceptance["settlement"]["event_id"]),
                    f["actor"].user_id,
                ),
            )
    monkeypatch.setattr(reports, "open_connection", lambda: psycopg.connect(url))
    result = (
        reports.PostgresFinancialStatementsRepository()
        .load_statement_pack(period_id=f["period"])
        .reporting_supplement["cash_flows"]
    )
    assert result["reconciled"] is (case == "valid")
    if case == "valid":
        assert result["net_cash_flow"] == "110.00"
        assert result["categories"]["operating"] == {
            "receipts": "110.00",
            "payments": "0.00",
            "net": "110.00",
        }
    else:
        assert result["status"] == "classification_required"
        assert result["net_cash_flow"] is None
    assert all("collector_cash" not in line for line in result["cash_lines"])
