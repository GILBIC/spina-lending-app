"""Real scopes, source changes, revision races and populated retained recovery."""

import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import psycopg
import pytest
import run_release_recovery_drill as recovery
from collector_accounting_test_support import accepted, post, prepare
from gilbic_backend.journal_disclosure_repository import read_journal_disclosures
from psycopg.rows import dict_row
from test_accounting_book_postgres import configure
from test_collector_liability_accounting_postgres import (
    collector_accounting as _collector_accounting,
)
from test_current_schema_accounting_cycle_postgres import (
    fresh_current_database as _fresh_current_database,
)
from test_financial_statement_snapshot_postgres import (
    isolated_statement_database as _isolated_statement_database,
)
from test_journal_disclosure_postgres import (
    add_mixed_journal,
    financing_policy,
    read_report,
    retain,
    review_payload,
)
from test_liability_control_postgres import register
from test_period_close_postgres import _management_actor, _move_to_review, _period
from test_reporting_policy_postgres import policy

collector_accounting = _collector_accounting
fresh_current_database = _fresh_current_database
isolated_statement_database = _isolated_statement_database


def seed(url):
    with psycopg.connect(url) as conn:
        actor = _management_actor(conn, uuid4().hex)
        book = configure(conn, actor, "owner_operations")
        period, day, _ = _period(conn, actor_id=actor, suffix=uuid4().hex)
        f = {"conn": conn, "actor": actor, "book": book, "period": period, "day": day}
        f["policy"] = policy(f)
        add_mixed_journal(f)
        f["disclosure_policy"] = financing_policy(f)
        f["payload"] = review_payload(f)
        return {key: value for key, value in f.items() if key != "conn"}


def test_private_scope_applies_before_any_totals_even_without_policy(
    collector_accounting,
):
    f = collector_accounting
    acceptance = accepted(f)
    journal = post(f, prepare(f, "settlement", UUID(acceptance["settlement"]["id"])))
    conn = f["conn"]
    with conn.cursor(row_factory=dict_row) as cursor:
        report = read_journal_disclosures(cursor, f["period"], f["actor"].user_id)
    assert any(row["journal_entry_id"] == str(journal) for row in report["journals"])
    conn.execute(
        "UPDATE treasury.account_access SET private_history=false WHERE account_id=%s AND user_id=%s",
        (f["wallet"], f["actor"].user_id),
    )
    with (
        pytest.raises(psycopg.Error, match="private Treasury"),
        conn.transaction(),
        conn.cursor(row_factory=dict_row) as cursor,
    ):
        read_journal_disclosures(cursor, f["period"], f["actor"].user_id)


def test_collector_source_correction_cannot_be_hidden_by_disclosure(
    collector_accounting,
):
    f = collector_accounting
    acceptance = accepted(f)
    prepared = prepare(f, "settlement", UUID(acceptance["settlement"]["id"]))
    journal = post(f, prepared)
    conn = f["conn"]
    assert (
        conn.execute(
            "SELECT accounting.journal_disclosure_source_status(%s) AS status",
            (journal,),
        ).fetchone()["status"]
        == "current"
    )
    event = conn.execute(
        "SELECT event_id FROM accounting.collector_liability_postings WHERE journal_entry_id=%s",
        (journal,),
    ).fetchone()["event_id"]
    conn.execute(
        "INSERT INTO treasury.event_revisions(id,event_id,version,action,classification,reason,actor_id) VALUES(%s,%s,2,'correct',NULL,'Synthetic corrected evidence',%s)",
        (uuid4(), event, f["actor"].user_id),
    )
    assert (
        conn.execute(
            "SELECT accounting.journal_disclosure_source_status(%s) AS status",
            (journal,),
        ).fetchone()["status"]
        == "source_correction_required"
    )


def test_simultaneous_revisions_have_one_winner(isolated_statement_database):
    url = isolated_statement_database
    f = seed(url)

    def attempt():
        with psycopg.connect(url) as conn:
            try:
                return str(
                    retain(f | {"conn": conn}, f["disclosure_policy"], f["payload"])
                )
            except psycopg.Error as error:
                return error.sqlstate

    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.submit(attempt), pool.submit(attempt)
        values = [a.result(timeout=30), b.result(timeout=30)]
    assert values.count("55000") == 1
    with psycopg.connect(url) as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM accounting.journal_disclosure_reviews"
            ).fetchone()[0]
            == 1
        )


def test_audit_failure_rolls_back_review_and_exact_retry_recovers(
    isolated_statement_database,
):
    url = isolated_statement_database
    f = seed(url)
    request = uuid4()
    with psycopg.connect(url) as conn:
        conn.execute(
            "CREATE FUNCTION public.fail_disclosure_test() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.action='accounting.journal_disclosure.retained' THEN RAISE EXCEPTION 'Synthetic audit failure'; END IF; RETURN NEW; END $$"
        )
        conn.execute(
            "CREATE TRIGGER fail_disclosure_test BEFORE INSERT ON core.audit_logs FOR EACH ROW EXECUTE FUNCTION public.fail_disclosure_test()"
        )
        with (
            pytest.raises(psycopg.Error, match="Synthetic audit failure"),
            conn.transaction(),
        ):
            retain(f | {"conn": conn}, f["disclosure_policy"], f["payload"], request)
        assert (
            conn.execute(
                "SELECT count(*) FROM accounting.journal_disclosure_reviews"
            ).fetchone()[0]
            == 0
        )
        conn.execute("DROP TRIGGER fail_disclosure_test ON core.audit_logs")
        assert (
            retain(f | {"conn": conn}, f["disclosure_policy"], f["payload"], request)
            == request
        )
        assert (
            retain(f | {"conn": conn}, f["disclosure_policy"], f["payload"], request)
            == request
        )


def test_period_review_captures_disclosures_and_freezes_new_versions(
    isolated_statement_database,
):
    url = isolated_statement_database
    f = seed(url)
    request = uuid4()
    with psycopg.connect(url) as conn:
        register(f | {"conn": conn}, UUID(f["lines"][2]), kind="borrowing_external")
        retain(f | {"conn": conn}, f["disclosure_policy"], f["payload"], request)
        _move_to_review(conn, f["period"], f["actor"])
        retained = conn.execute(
            "SELECT source_snapshot#>'{additional_evidence,journal_disclosure_reviews}' "
            "FROM accounting.period_review_manifests WHERE fiscal_period_id=%s",
            (f["period"],),
        ).fetchone()[0]
        assert retained[0]["id"] == str(request)
        assert retained[0]["payload"] == f["payload"]
        assert (
            retain(f | {"conn": conn}, f["disclosure_policy"], f["payload"], request)
            == request
        )
        with pytest.raises(psycopg.Error, match="open period"), conn.transaction():
            retain(
                f | {"conn": conn},
                f["disclosure_policy"],
                f["payload"] | {"expected_version": 1},
            )


def test_period_transition_wins_before_pending_disclosure_retention(
    isolated_statement_database,
):
    url = isolated_statement_database
    f = seed(url)
    with psycopg.connect(url) as conn:
        register(f | {"conn": conn}, UUID(f["lines"][2]), kind="borrowing_external")
    started = Event()

    def write():
        with psycopg.connect(
            url, application_name="disclosure-transition-race"
        ) as conn:
            conn.execute("SET statement_timeout='10s'")
            started.set()
            try:
                return str(
                    retain(f | {"conn": conn}, f["disclosure_policy"], f["payload"])
                )
            except psycopg.Error as error:
                return error.sqlstate

    with ThreadPoolExecutor(max_workers=1) as pool:
        with psycopg.connect(url) as closing:
            # The real period-transition boundary is held before source capture.
            closing.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended('period-close:'||%s,0))",
                (str(f["period"]),),
            )
            future = pool.submit(write)
            assert started.wait(5)
            with psycopg.connect(url, autocommit=True) as observer:
                deadline = time.monotonic() + 5
                blocked = False
                while not future.done() and time.monotonic() < deadline:
                    blocked = observer.execute(
                        "SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE application_name='disclosure-transition-race' AND %s=ANY(pg_blocking_pids(pid)))",
                        (closing.info.backend_pid,),
                    ).fetchone()[0]
                    if blocked:
                        break
                    time.sleep(0.02)
                try:
                    assert blocked, (
                        "Disclosure write crossed the in-progress period transition"
                    )
                    _move_to_review(closing, f["period"], f["actor"])
                finally:
                    closing.commit()
        assert future.result(timeout=15) == "55000"
    with psycopg.connect(url) as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM accounting.journal_disclosure_reviews"
            ).fetchone()[0]
            == 0
        )


def test_populated_disclosure_restore_preserves_report_and_audits(
    fresh_current_database, tmp_path
):
    case = fresh_current_database
    f = seed(case["source"])
    with psycopg.connect(case["source"]) as conn:
        retain(f | {"conn": conn}, f["disclosure_policy"], f["payload"])
        expected_report = read_report(f | {"conn": conn})
        expected_rows = recovery.database_snapshot(conn)
    assert expected_rows["accounting.journal_disclosure_reviews"]["rows"] == 1
    binary = Path(os.environ["SPINA_POSTGRES_BIN"]) / (
        "pg_dump.exe" if os.name == "nt" else "pg_dump"
    )
    archive = tmp_path / "disclosures.dump"
    recovery.run_pg(
        binary,
        ["--format=custom", "--file", str(archive)],
        recovery.pg_environment(case["params"], case["names"][0]),
    )
    recovery.run_pg(
        binary.with_name("pg_restore.exe" if os.name == "nt" else "pg_restore"),
        ["--exit-on-error", "--no-owner", "--dbname", case["names"][1], str(archive)],
        recovery.pg_environment(case["params"], case["names"][1]),
    )
    with psycopg.connect(case["restore"]) as conn:
        recovery.verify_database(conn, expected_rows)
        assert read_report(f | {"conn": conn}) == expected_report
