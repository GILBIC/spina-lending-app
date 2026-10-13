"""Statement reads derive internal groups from actual retained transfer audits."""

from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row, tuple_row
from psycopg.types.json import Jsonb
from test_financial_statement_snapshot_postgres import (
    isolated_statement_database as _isolated_statement_database,
)
from test_reporting_policy_postgres import policy
from test_treasury_receipt_accounting_postgres import (
    SQL_ROOT,
    install,
)
from test_treasury_receipt_accounting_postgres import (
    post as post_receipt,
)
from test_treasury_receipt_accounting_postgres import (
    prepare as prepare_receipt,
)
from test_treasury_transfer_accounting_postgres import (
    MIGRATION,
    post,
    prepare,
    record_leg,
    seed_transfer,
)

from gilbic_backend import financial_statements_repository as reports

isolated_statement_database = _isolated_statement_database


@pytest.mark.parametrize(
    "case", ["valid", "correction", "gross_operating", "gross_mixed", "gross_corrected"]
)
def test_statement_uses_only_current_exact_transfer_principal_proof(
    isolated_statement_database, monkeypatch, tmp_path, case
):
    url = isolated_statement_database
    with psycopg.connect(url, row_factory=dict_row) as conn:
        f = seed_transfer(conn, tmp_path)
        install(conn, MIGRATION)
        install(conn, SQL_ROOT / "0150_add_reporting_evidence.sql")
        receipt = post_receipt(f, prepare_receipt(f, f["source_mapping"]))
        record_leg(f, "source", fee="2.00")
        source = post(f, prepare(f, "source"))
        record_leg(f, "destination")
        destination = post(f, prepare(f, "destination"))
        conn.row_factory = tuple_row
        selected = policy(f | {"actor": f["actor"].user_id})
        conn.row_factory = dict_row
        for journal, allocations in (
            (receipt, [{"category": "operating", "amount": "147.25"}]),
            (
                source,
                [
                    {"category": "internal", "amount": "-100.00"},
                    {"category": "operating", "amount": "-2.00"},
                ],
            ),
            (destination, [{"category": "internal", "amount": "100.00"}]),
        ):
            if case.startswith("gross_") and journal == source:
                allocations = [{"category": "operating", "amount": "-102.00"}]
            elif case.startswith("gross_") and journal == destination:
                allocations = [
                    {
                        "category": "operating"
                        if case != "gross_mixed"
                        else "financing",
                        "amount": "100.00",
                    }
                ]
            line = conn.execute(
                "SELECT l.id,l.debit-l.credit AS amount FROM accounting.journal_lines l JOIN accounting.accounts a ON a.id=l.account_id WHERE l.journal_entry_id=%s AND a.code='1030'",
                (journal,),
            ).fetchone()
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
                            "evidence_reference": "test:owned-transfer-classification",
                            "evidence_digest": "a" * 64,
                            "reviewed": True,
                        }
                    ),
                    f["actor"].user_id,
                ),
            )
        if case in {"correction", "gross_corrected"}:
            conn.execute(
                "INSERT INTO treasury.event_revisions(id,event_id,version,action,reason,actor_id) SELECT %s,source_event_id,2,'correct','Synthetic new corrected source observation',%s FROM treasury.transfers WHERE id=%s",
                (uuid4(), f["actor"].user_id, f["transfer"]),
            )
    monkeypatch.setattr(reports, "open_connection", lambda: psycopg.connect(url))
    result = (
        reports.PostgresFinancialStatementsRepository()
        .load_statement_pack(period_id=f["period"])
        .reporting_supplement["cash_flows"]
    )
    if case != "valid":
        assert result["status"] == "classification_required"
        assert result["reconciled"] is False
    else:
        assert result["status"] == "complete_for_posted_ledger"
        assert result["reconciled"] is True
        assert result["net_cash_flow"] == "145.25"
        assert result["categories"]["operating"] == {
            "receipts": "147.25",
            "payments": "2.00",
            "net": "145.25",
        }
    assert all("internal_transfer" not in line for line in result["cash_lines"])
