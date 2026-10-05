"""Actual committed source races recheck evidence after waiting on the wallet."""

import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import psycopg
import pytest
from psycopg.rows import dict_row
from test_financial_statement_snapshot_postgres import (
    isolated_statement_database as _isolated_statement_database,
)
from test_treasury_application_accounting_postgres import MIGRATION
from test_treasury_receipt_accounting_postgres import install, seed
from treasury_application_accounting_test_support import (
    additional_loan_gl,
    application_post,
    application_prepare,
    create_application_source,
    late_prior_collection,
)

isolated_statement_database = _isolated_statement_database


@pytest.mark.parametrize("winner", ["post", "earlier_source", "ledger"])
def test_waiting_application_post_uses_current_committed_evidence(
    isolated_statement_database, monkeypatch, winner
):
    url = isolated_statement_database
    with psycopg.connect(url, row_factory=dict_row) as setup:
        base = seed(setup)
        install(setup, MIGRATION)
        f = create_application_source(
            base, monkeypatch, collection_delay=1 if winner == "earlier_source" else 0
        )
        prep = application_prepare(f)
    waiting = Event()
    waiter_pid = []

    def waiting_post():
        with psycopg.connect(url, row_factory=dict_row) as connection:
            connection.execute("SET statement_timeout='10s'")
            waiter_pid.append(connection.info.backend_pid)
            waiting.set()
            return application_post(f | {"conn": connection}, prep)

    with (
        psycopg.connect(url, row_factory=dict_row) as winner_connection,
        psycopg.connect(url, autocommit=True) as observer,
        ThreadPoolExecutor(max_workers=1) as workers,
    ):
        winner_connection.execute(
            "SELECT id FROM treasury.accounts WHERE id=%s FOR UPDATE", (f["wallet"],)
        )
        current = f | {"conn": winner_connection}
        if winner == "post":
            expected = application_post(current, prep)
        elif winner == "earlier_source":
            late_prior_collection(current)
        else:
            additional_loan_gl(current)
        future = workers.submit(waiting_post)
        assert waiting.wait(timeout=5)
        deadline = time.monotonic() + 5
        blocked = False
        while time.monotonic() < deadline:
            blocked = observer.execute(
                "SELECT cardinality(pg_blocking_pids(%s))>0", (waiter_pid[0],)
            ).fetchone()[0]
            if blocked:
                break
            time.sleep(0.01)
        assert blocked, "Application post did not wait on the retained account lock"
        winner_connection.commit()
        if winner == "post":
            assert future.result(timeout=10) == expected
        else:
            with pytest.raises(
                psycopg.Error, match="prior loan source|carrying components|stale"
            ):
                future.result(timeout=10)
    with psycopg.connect(url) as check:
        assert check.execute(
            "SELECT count(*) FROM accounting.treasury_application_postings WHERE application_id=%s",
            (f["application"],),
        ).fetchone()[0] == (1 if winner == "post" else 0)
