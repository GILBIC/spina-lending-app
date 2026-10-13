"""Payout accounting rechecks committed authority and source after wallet lock waits."""

import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import psycopg
import pytest
from psycopg.rows import dict_row
from test_first_loan_postgres import (
    private_fixture_configuration as _private_fixture_configuration,
)
from test_loan_payout_accounting_boundaries_postgres import (
    actual,
    correction,
    post,
    retained,
)
from test_loan_payout_accounting_postgres import payout_accounting as _payout_accounting
from test_loan_payout_accounting_postgres import payout_database as _payout_database

private_fixture_configuration = _private_fixture_configuration
payout_accounting = _payout_accounting
payout_database = _payout_database


@pytest.mark.parametrize("winner", ["post", "correction", "permission"])
def test_waiting_payout_post_rechecks_committed_source_and_authority(
    payout_accounting, payout_database, winner
):
    f = payout_accounting
    payout = actual(f)["target_id"]
    prepared = retained(f, payout)
    f["conn"].commit()
    waiting = Event()
    waiter_pid = []

    def waiting_post():
        with psycopg.connect(payout_database, row_factory=dict_row) as conn:
            conn.execute("SET statement_timeout='10s'")
            waiter_pid.append(conn.info.backend_pid)
            waiting.set()
            return post(f | {"conn": conn}, prepared)

    with (
        psycopg.connect(payout_database, row_factory=dict_row) as first,
        psycopg.connect(payout_database, autocommit=True) as observer,
        ThreadPoolExecutor(max_workers=1) as workers,
    ):
        first.execute(
            "SELECT id FROM treasury.accounts WHERE id=%s FOR UPDATE", (f["wallet"],)
        )
        if winner == "post":
            expected = post(f | {"conn": first}, prepared)
        elif winner == "correction":
            correction(f | {"conn": first}, payout)
        else:
            first.execute(
                "UPDATE treasury.account_access SET private_history=false WHERE account_id=%s",
                (f["wallet"],),
            )
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
        assert blocked, "Payout post did not wait on the actual wallet lock"
        first.commit()
        if winner == "post":
            assert future.result(timeout=10) == expected
        else:
            with pytest.raises(psycopg.Error):
                future.result(timeout=10)
    assert f["conn"].execute(
        "SELECT count(*) AS n FROM accounting.loan_payout_accounting_postings WHERE payout_id=%s",
        (payout,),
    ).fetchone()["n"] == (1 if winner == "post" else 0)
