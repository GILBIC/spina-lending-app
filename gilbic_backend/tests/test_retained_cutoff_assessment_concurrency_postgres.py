"""A source commit wins safely on either side of an assessment confirmation."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep

import psycopg
import pytest
from test_financial_statement_snapshot_postgres import (
    isolated_statement_database as _isolated_statement_database,
)
from test_retained_cutoff_assessment_postgres import (
    _backdated_collection,
    _exact,
    _post,
    _prepare,
    _seed,
)

isolated_statement_database = _isolated_statement_database


@pytest.mark.parametrize("winner", ["source", "confirmation"])
def test_cutoff_assessment_waits_and_rechecks_actual_source(
    isolated_statement_database, winner
):
    url = isolated_statement_database
    with psycopg.connect(url) as setup:
        case = _seed(setup)
        prepared, digest = _prepare(case)
    waiter_started = Event()
    waiter_pid = []

    def waiting_operation():
        with psycopg.connect(url) as conn:
            conn.execute("SET statement_timeout='10s'")
            waiter_pid.append(conn.info.backend_pid)
            waiter_started.set()
            f = case | {"conn": conn}
            return (
                _post(f, prepared, digest)
                if winner == "source"
                else _backdated_collection(f)
            )

    with (
        psycopg.connect(url) as first,
        psycopg.connect(url, autocommit=True) as observer,
        ThreadPoolExecutor(max_workers=1) as pool,
    ):
        first.execute("SET statement_timeout='10s'")
        f = case | {"conn": first}
        first_result = (
            _backdated_collection(f)
            if winner == "source"
            else _post(f, prepared, digest)
        )
        future = pool.submit(waiting_operation)
        assert waiter_started.wait(timeout=5)
        deadline = monotonic() + 5
        blocked = False
        while monotonic() < deadline:
            blocked = observer.execute(
                "SELECT cardinality(pg_blocking_pids(%s))>0", (waiter_pid[0],)
            ).fetchone()[0]
            if blocked:
                break
            sleep(0.01)
        assert blocked, "Assessment/source did not wait on authoritative source locks"
        first.commit()
        if winner == "source":
            with pytest.raises(psycopg.Error, match="changed or is blocked"):
                future.result(timeout=10)
            source = first_result
        else:
            source = future.result(timeout=10)
    with psycopg.connect(url) as check:
        assert (
            check.execute(
                "SELECT amount FROM lending.collection_transactions WHERE id=%s",
                (source,),
            ).fetchone()[0]
            == 1
        )
        assert not _exact(case | {"conn": check})
        assert check.execute(
            "SELECT count(*) FROM accounting.loan_period_assessment_postings WHERE preparation_id=%s",
            (prepared,),
        ).fetchone()[0] == (winner == "confirmation")
