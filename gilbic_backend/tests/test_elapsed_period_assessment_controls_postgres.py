"""Historical cutoff posting serializes with actual sources and preserves meaning."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep

import psycopg
import pytest
from test_elapsed_period_assessment_postgres import (
    _collection,
    _exact,
    _post,
    _prepare,
    _seed,
)
from test_elapsed_period_assessment_postgres import (
    elapsed_assessment as _elapsed_assessment,
)
from test_financial_statement_snapshot_postgres import (
    isolated_statement_database as _isolated_statement_database,
)

elapsed_assessment = _elapsed_assessment
isolated_statement_database = _isolated_statement_database


def test_deferred_assessment_rejects_same_transaction_backdated_source(
    elapsed_assessment,
):
    f = elapsed_assessment
    prepared, digest = _prepare(f)
    with (
        pytest.raises(psycopg.Error, match="Historical assessment source changed"),
        f["conn"].transaction(),
    ):
        _post(f, prepared, digest)
        _collection(f, f["cutoff"])
        assert _exact(f) is False
        f["conn"].execute("SET CONSTRAINTS ALL IMMEDIATE")
    assert (
        f["conn"]
        .execute(
            "SELECT count(*) FROM accounting.loan_elapsed_assessment_postings WHERE preparation_id=%s",
            (prepared,),
        )
        .fetchone()[0]
        == 0
    )
    assert (
        f["conn"]
        .execute(
            "SELECT count(*) FROM accounting.journal_entries WHERE source_reference=%s",
            (str(prepared),),
        )
        .fetchone()[0]
        == 0
    )


@pytest.mark.parametrize("code", ["1100", "1120", "1190", "4000", "5000"])
def test_changed_chart_meaning_cannot_post_prepared_historical_amounts(
    elapsed_assessment,
    code,
):
    f = elapsed_assessment
    prepared, digest = _prepare(f)
    f["conn"].execute(
        "UPDATE accounting.accounts SET normal_balance=CASE normal_balance WHEN 'debit' THEN 'credit' ELSE 'debit' END WHERE code=%s",
        (code,),
    )
    with (
        pytest.raises(psycopg.Error, match="source changed|blocked|definition"),
        f["conn"].transaction(),
    ):
        _post(f, prepared, digest)
    assert (
        f["conn"]
        .execute(
            "SELECT count(*) FROM accounting.loan_elapsed_assessment_postings WHERE preparation_id=%s",
            (prepared,),
        )
        .fetchone()[0]
        == 0
    )


@pytest.mark.parametrize("winner", ["source", "assessment"])
def test_historical_post_rechecks_sources_after_concurrent_lock_wait(
    isolated_statement_database,
    winner,
):
    url = isolated_statement_database
    with psycopg.connect(url) as setup:
        f = _seed(setup)
        prepared, digest = _prepare(f)
    started, waiting_pid = Event(), []

    def waiting():
        with psycopg.connect(url) as conn:
            conn.execute("SET statement_timeout='30s'")
            waiting_pid.append(conn.info.backend_pid)
            started.set()
            if winner == "source":
                return _post(f | {"conn": conn}, prepared, digest)
            return _collection(f | {"conn": conn}, f["cutoff"])

    with (
        psycopg.connect(url) as first,
        psycopg.connect(url, autocommit=True) as observer,
        ThreadPoolExecutor(max_workers=1) as pool,
    ):
        first.execute("SET statement_timeout='30s'")
        if winner == "source":
            _collection(f | {"conn": first}, f["cutoff"])
        else:
            _post(f | {"conn": first}, prepared, digest)
        future = pool.submit(waiting)
        assert started.wait(timeout=5)
        deadline = monotonic() + 5
        blocked = False
        while monotonic() < deadline:
            blocked = observer.execute(
                "SELECT cardinality(pg_blocking_pids(%s))>0", (waiting_pid[0],)
            ).fetchone()[0]
            if blocked:
                break
            sleep(0.01)
        assert blocked, "Actual source insertion must serialize with historical posting"
        first.commit()
        if winner == "source":
            with pytest.raises(psycopg.Error, match="source changed|blocked"):
                future.result(timeout=30)
        else:
            future.result(timeout=30)
    with psycopg.connect(url) as check:
        assert _exact(f | {"conn": check}) is False
        assert (
            check.execute(
                "SELECT count(*) FROM lending.collection_transactions WHERE loan_id=%s AND amount=1",
                (f["loan"],),
            ).fetchone()[0]
            == 1
        )
        assert check.execute(
            "SELECT count(*) FROM accounting.loan_elapsed_assessment_postings WHERE preparation_id=%s",
            (prepared,),
        ).fetchone()[0] == (1 if winner == "assessment" else 0)
