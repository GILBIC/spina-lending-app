"""Fresh final-schema accounting and populated recovery, without legacy reinstalls."""

import os
import re
import shutil
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
import run_release_recovery_drill as recovery
import run_stage5d17_disposable_postgres_validation as bootstrap
from gilbic_backend.financial_statements_api import _pack_payload
from gilbic_backend.office_review_evidence_storage import PrivateEvidenceStore
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from test_liability_control_postgres import register
from test_period_close_postgres import _manual_journal, _move_to_review, _post_close
from test_reporting_policy_postgres import policy
from test_treasury_receipt_accounting_postgres import (
    RECEIPT_FILE,
    mapping,
    post,
    prepare,
    seed,
)

from gilbic_backend import financial_statements_repository as reports

SQL_ROOT = Path(__file__).resolve().parents[1] / "sql"
THROUGH = 149


@pytest.fixture
def fresh_current_database():
    url = os.getenv("GILBIC_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Explicit disposable loopback PostgreSQL URL required")
    assert os.getenv("SPINA_ALLOW_DISPOSABLE_DATABASE") == "1"
    through = int(os.getenv("SPINA_CURRENT_SCHEMA_THROUGH", str(THROUGH)))
    assert through >= THROUGH, "The current-schema cycle cannot verify an older schema"
    params = bootstrap._safe_local_connection_params(url)
    assert not {"options", "passfile", "service", "servicefile"}.intersection(params)
    token = uuid4().hex[:24]
    names = [
        "spina_accounting_current_" + kind + "_" + token
        for kind in ("source", "restore")
    ]
    admin_url = make_conninfo(**(params | {"dbname": "postgres"}))
    created = []
    with psycopg.connect(admin_url, autocommit=True) as admin:
        try:
            for name in names:
                admin.execute(
                    sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(
                        sql.Identifier(name)
                    )
                )
                created.append(name)
            source_url = make_conninfo(**(params | {"dbname": names[0]}))
            bootstrap._install_supabase_auth_prerequisite(source_url)
            migrations = sorted(
                path
                for path in SQL_ROOT.glob("*.sql")
                if path.name[:4].isdigit() and int(path.name[:4]) <= through
            )
            assert any(path.name.startswith(f"{through:04d}_") for path in migrations)
            with psycopg.connect(source_url, autocommit=True) as conn:
                for migration in migrations:
                    conn.execute(migration.read_text(encoding="utf-8"))
            yield {
                "params": params,
                "names": names,
                "source": source_url,
                "restore": make_conninfo(**(params | {"dbname": names[1]})),
            }
        finally:
            for name in reversed(created):
                assert re.fullmatch(
                    r"spina_accounting_current_(source|restore)_[a-f0-9]{24}", name
                )
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


def _seed_supported_cycle(url, private_root):
    with psycopg.connect(url, row_factory=dict_row) as conn:
        f = seed(conn, install_migrations=False)
        PrivateEvidenceStore(private_root).put(
            f["evidence"], RECEIPT_FILE, "application/pdf"
        )
        receipt_journal = post(f, prepare(f, mapping(f)))
        actor = f["actor"].user_id
        # Existing helper consumes positional result rows; use a tuple-row cursor
        # connection for the same committed case below, without changing schema.
    with psycopg.connect(url) as conn:
        selected = policy(f | {"conn": conn, "actor": actor})
        payable, _ = _manual_journal(
            conn,
            actor_id=actor,
            posting_date=f["day"],
            description="Synthetic actual supplier obligation",
            lines=[
                {"account_code": "5200", "debit": "100.00", "credit": "0"},
                {"account_code": "2000", "debit": "0", "credit": "100.00"},
            ],
        )
        liability_line = conn.execute(
            "SELECT id FROM accounting.journal_lines WHERE journal_entry_id=%s AND line_number=2",
            (payable,),
        ).fetchone()[0]
        register(f | {"conn": conn, "actor": actor}, liability_line)
        cash_line = conn.execute(
            "SELECT id FROM accounting.journal_lines WHERE journal_entry_id=%s AND line_number=1",
            (receipt_journal,),
        ).fetchone()[0]
        conn.execute(
            "SELECT accounting.retain_cash_flow_classification(%s,%s,%s,%s,%s)",
            (
                uuid4(),
                f["book"],
                selected,
                Jsonb(
                    {
                        "journal_line_id": str(cash_line),
                        "expected_amount": "147.25",
                        "expected_version": 0,
                        "allocations": [{"category": "operating", "amount": "147.25"}],
                        "evidence_reference": "test:borrower-receipt-cash-flow",
                        "evidence_digest": "a" * 64,
                        "reviewed": True,
                    }
                ),
                actor,
            ),
        )
        assert (
            conn.execute(
                "SELECT count(*) FROM accounting.period_source_blockers(%s)",
                (f["period"],),
            ).fetchone()[0]
            == 0
        )
        _move_to_review(conn, f["period"], actor)
        prepared = conn.execute(
            "SELECT accounting.prepare_period_close(%s,%s)", (f["period"], actor)
        ).fetchone()[0]
        digest, net, end = conn.execute(
            "SELECT p.close_digest,p.net_income,f.end_date FROM accounting.period_close_preparations p JOIN accounting.fiscal_periods f ON f.id=p.fiscal_period_id WHERE p.id=%s",
            (prepared,),
        ).fetchone()
        _post_close(
            conn,
            period_id=f["period"],
            actor_id=actor,
            token="c" * 64,
            close_digest=digest,
            net_income=str(net),
            end_date=end,
        )
    return f | {"actor_id": actor}


def _report(url, period, monkeypatch):
    monkeypatch.setattr(reports, "open_connection", lambda: psycopg.connect(url))
    return _pack_payload(
        reports.PostgresFinancialStatementsRepository().load_statement_pack(
            period_id=period
        )
    )


def test_current_schema_receipt_payable_close_and_statements_reconcile(
    fresh_current_database, tmp_path, monkeypatch
):
    url = fresh_current_database["source"]
    f = _seed_supported_cycle(url, tmp_path / "private")
    report = _report(url, f["period"], monkeypatch)
    with psycopg.connect(url) as conn:
        balances = dict(
            conn.execute(
                "SELECT a.code,sum(l.debit-l.credit) FROM accounting.journal_lines l JOIN accounting.journal_entries j ON j.id=l.journal_entry_id JOIN accounting.accounts a ON a.id=l.account_id WHERE j.status='posted' GROUP BY a.code"
            ).fetchall()
        )
        assert (
            conn.execute(
                "SELECT status FROM accounting.fiscal_periods WHERE id=%s",
                (f["period"],),
            ).fetchone()[0]
            == "closed"
        )
        assert (
            conn.execute(
                "SELECT outstanding_amount FROM accounting.liability_control_schedule(%s)",
                (f["day"],),
            ).fetchone()[0]
            == 100
        )
        assert sum(balances.values()) == 0
        assert str(balances["1030"]) == "147.25"
        assert str(balances["2200"]) == "-147.25"
        assert balances["2000"] == -100 and balances["3100"] == 100
    supplement = report["reporting_supplement"]
    assert supplement["cash_flows"]["closing_cash"] == "147.25"
    assert supplement["cash_flows"]["reconciled"] is True
    assert supplement["changes_in_equity"]["closing_equity"] == "-100.00"
    assert supplement["changes_in_equity"]["reconciled"] is True


def test_current_schema_populated_private_evidence_restores_exactly(
    fresh_current_database, tmp_path, monkeypatch
):
    case = fresh_current_database
    private = tmp_path / "private"
    f = _seed_supported_cycle(case["source"], private)
    expected_report = _report(case["source"], f["period"], monkeypatch)
    suffix = ".exe" if os.name == "nt" else ""
    configured = os.getenv("SPINA_POSTGRES_BIN")
    binary = (
        Path(configured) / ("pg_dump" + suffix)
        if configured
        else Path(shutil.which("pg_dump") or "__missing_pg_dump__")
    )
    restore = binary.with_name("pg_restore" + suffix)
    assert binary.is_file() and restore.is_file(), (
        "Explicit matching PostgreSQL dump/restore tools are required"
    )
    with psycopg.connect(case["source"]) as conn:
        expected_rows = recovery.database_snapshot(conn)
    expected_files = recovery.file_manifest(private)
    assert expected_rows["accounting.treasury_receipt_postings"]["rows"] == 1
    assert expected_rows["accounting.liability_obligations"]["rows"] == 1
    assert expected_rows["accounting.reporting_policy_versions"]["rows"] == 1
    assert expected_files
    expected_schema = recovery.schema_snapshot(
        binary,
        recovery.pg_environment(case["params"], case["names"][0]),
        case["source"],
    )
    (tmp_path / "source-schema.sql").write_bytes(
        recovery.run_pg(
            binary,
            ["--schema-only", "--no-owner", "--no-comments"],
            recovery.pg_environment(case["params"], case["names"][0]),
        )
    )
    archive = tmp_path / "synthetic-accounting.dump"
    recovery.run_pg(
        binary,
        ["--format=custom", "--file", str(archive)],
        recovery.pg_environment(case["params"], case["names"][0]),
    )
    assert archive.stat().st_size > 0
    restored_private = tmp_path / "restored-private"
    shutil.copytree(private, restored_private)
    recovery.run_pg(
        restore,
        ["--exit-on-error", "--no-owner", "--dbname", case["names"][1], str(archive)],
        recovery.pg_environment(case["params"], case["names"][1]),
    )
    with psycopg.connect(case["restore"]) as conn:
        recovery.verify_database(conn, expected_rows)
    recovery.verify_files(restored_private, expected_files)
    (tmp_path / "restored-schema.sql").write_bytes(
        recovery.run_pg(
            binary,
            ["--schema-only", "--no-owner", "--no-comments"],
            recovery.pg_environment(case["params"], case["names"][1]),
        )
    )
    assert (
        recovery.schema_snapshot(
            binary,
            recovery.pg_environment(case["params"], case["names"][1]),
            case["restore"],
        )
        == expected_schema
    )
    assert _report(case["restore"], f["period"], monkeypatch) == expected_report
