"""Real first-book range export uses a single authorized read-only connection."""

from contextlib import contextmanager
from datetime import timedelta
from uuid import uuid4

import psycopg
import pytest
from gilbic_backend.accounting_export import build_accounting_export
from psycopg.rows import dict_row, tuple_row
from psycopg.types.json import Jsonb
from test_accounting_book_postgres import configure
from test_financial_statement_snapshot_postgres import (
    isolated_statement_database as _isolated_statement_database,
)
from test_initial_capital_funding_postgres import _post, _record
from test_period_close_postgres import _management_actor, _period

from gilbic_backend import accounting_export_repository as exports
from gilbic_backend import financial_statements_repository as statements

isolated_statement_database = _isolated_statement_database


def test_first_book_export_contains_real_range_and_no_invented_prior_year(
    isolated_statement_database, monkeypatch
):
    url = isolated_statement_database
    with psycopg.connect(url) as conn:
        actor = _management_actor(conn, uuid4().hex)
        configure(conn, actor, "owner_operations")
        period, start, end = _period(conn, actor_id=actor, suffix=uuid4().hex)
        evidence = _record(
            conn,
            actor_id=actor,
            key=uuid4(),
            funding_date=start,
            amount="123.45",
            cash_code="1010",
            suffix=uuid4().hex,
        )
        conn.execute(
            "SELECT accounting.prepare_initial_capital_funding_journal(%s,%s)",
            (evidence, actor),
        )
        _post(
            conn,
            evidence_id=evidence,
            actor_id=actor,
            token="b" * 64,
            digest="a" * 64,
            amount="123.45",
            cash_code="1010",
            posting_date=start,
            period_id=period,
        )
    connections = 0

    @contextmanager
    def opened():
        nonlocal connections
        connections += 1
        with psycopg.connect(url) as conn:
            yield conn
            assert (
                conn.execute("SHOW transaction_isolation").fetchone()[0]
                == "repeatable read"
            )
            assert conn.execute("SHOW transaction_read_only").fetchone()[0] == "on"

    def unexpected_connection():
        raise AssertionError("Statement export must reuse the export snapshot")

    monkeypatch.setattr(exports, "open_connection", opened)
    monkeypatch.setattr(statements, "open_connection", unexpected_connection)
    snapshot = exports.PostgresAccountingExportRepository().load_snapshot(
        start_date=start, end_date=end, actor_user_id=actor, include_reporting=True
    )
    assert connections == 1
    report = snapshot["reporting_review"]
    assert report["annual_consolidation"] == "full_range_posted_ledger"
    assert report["range_statements"]["financial_position"]["total_assets"] == "123.45"
    assert report["range_statements"]["profit_or_loss"]["net_income"] == "0.00"
    assert (
        report["range_statements"]["reporting_supplement"]["cash_flows"][
            "net_cash_flow"
        ]
        is None
    )
    assert report["range_statements"]["reporting_supplement"]["comparative"] is None
    assert build_accounting_export(
        snapshot, start_date=start, end_date=end, generated_by_user_id=actor
    ).startswith(b"PK")


def test_full_range_transfer_principal_close_and_private_export_authority(
    isolated_statement_database, monkeypatch, tmp_path
):
    import test_treasury_receipt_accounting_postgres as receipt
    import test_treasury_transfer_accounting_postgres as transfer
    from test_period_close_postgres import _move_to_review, _post_close
    from test_reporting_policy_postgres import policy

    url = isolated_statement_database
    # Run on the installed schema; the original fixture defaults to historical
    # migration reinstalls, which are intentionally disabled for this proof.
    monkeypatch.setattr(
        transfer, "seed", lambda conn: receipt.seed(conn, install_migrations=False)
    )
    with psycopg.connect(url, row_factory=dict_row) as conn:
        f = transfer.seed_transfer(conn, tmp_path)
        actor = f["actor"].user_id
        dates = conn.execute(
            "SELECT start_date,end_date FROM accounting.fiscal_periods WHERE id=%s",
            (f["period"],),
        ).fetchone()
        start, first_end = dates["start_date"], dates["end_date"]
        end = first_end + timedelta(days=10)
        second = conn.execute(
            "SELECT accounting.create_fiscal_period('Synthetic next reporting period',%s,%s,%s) AS id",
            (first_end + timedelta(days=1), end, actor),
        ).fetchone()["id"]
        inbound = receipt.post(f, receipt.prepare(f, f["source_mapping"]))
        transfer.record_leg(f, "source", fee="2.00")
        outbound = transfer.post(f, transfer.prepare(f, "source"))
        transfer.record_leg(f, "destination", day=first_end + timedelta(days=1))
        destination = transfer.post(f, transfer.prepare(f, "destination"))
        conn.row_factory = tuple_row
        policies = {
            p: policy(f | {"conn": conn, "actor": actor, "period": p})
            for p in (f["period"], second)
        }
        for journal, period in (
            (inbound, f["period"]),
            (outbound, f["period"]),
            (destination, second),
        ):
            line, amount = conn.execute(
                "SELECT l.id,l.debit-l.credit FROM accounting.journal_lines l JOIN accounting.accounts a ON a.id=l.account_id WHERE l.journal_entry_id=%s AND a.code='1030'",
                (journal,),
            ).fetchone()
            exact = format(amount, ".2f")
            conn.execute(
                "SELECT accounting.retain_cash_flow_classification(%s,%s,%s,%s,%s)",
                (
                    uuid4(),
                    f["book"],
                    policies[period],
                    Jsonb(
                        {
                            "journal_line_id": str(line),
                            "expected_amount": exact,
                            "expected_version": 0,
                            "allocations": [{"category": "operating", "amount": exact}],
                            "evidence_reference": "test:range-transfer",
                            "evidence_digest": "a" * 64,
                            "reviewed": True,
                        }
                    ),
                    actor,
                ),
            )
    monkeypatch.setattr(exports, "open_connection", lambda: psycopg.connect(url))
    repository = exports.PostgresAccountingExportRepository()

    def read():
        return repository.load_snapshot(
            start_date=start, end_date=end, actor_user_id=actor, include_reporting=True
        )["reporting_review"]["range_statements"]

    before = read()
    cash = before["reporting_supplement"]["cash_flows"]
    assert cash["categories"]["operating"] == {
        "receipts": "147.25",
        "payments": "2.00",
        "net": "145.25",
    }
    assert cash["reconciled"] is True
    assert before["profit_or_loss"]["net_income"] == "-2.00"
    assert before["reporting_supplement"]["changes_in_equity"]["reconciled"] is True
    with psycopg.connect(url) as conn:
        _move_to_review(conn, f["period"], actor)
        prepared = conn.execute(
            "SELECT accounting.prepare_period_close(%s,%s)", (f["period"], actor)
        ).fetchone()[0]
        digest, net = conn.execute(
            "SELECT close_digest,net_income FROM accounting.period_close_preparations WHERE id=%s",
            (prepared,),
        ).fetchone()
        _post_close(
            conn,
            period_id=f["period"],
            actor_id=actor,
            token="e" * 64,
            close_digest=digest,
            net_income=str(net),
            end_date=first_end,
        )
    after = read()
    assert after["profit_or_loss"] == before["profit_or_loss"]
    assert (
        after["reporting_supplement"]["changes_in_equity"]
        == before["reporting_supplement"]["changes_in_equity"]
    )
    assert (
        after["reporting_supplement"]["cash_flows"]["categories"] == cash["categories"]
    )
    with psycopg.connect(url) as conn:
        conn.execute(
            "UPDATE treasury.account_access SET private_history=false WHERE account_id=%s AND user_id=%s",
            (f["destination"], actor),
        )
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        read()
    # Even the earlier source leg contributes both owned private wallets.
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        repository.load_snapshot(
            start_date=start, end_date=first_end, actor_user_id=actor
        )
    with psycopg.connect(url) as conn:
        conn.execute(
            "UPDATE treasury.account_access SET private_history=true WHERE account_id=%s AND user_id=%s",
            (f["destination"], actor),
        )
        conn.execute("DELETE FROM core.user_roles WHERE user_id=%s", (actor,))
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        read()
