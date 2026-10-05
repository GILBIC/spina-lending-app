"""A valid proof clears real guards; later facts remain retained and visible."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep
from uuid import uuid4

import psycopg
import pytest
import test_period_close_postgres as close
import test_v1_tax_evidence_postgres as tax
import test_v1_tax_liability_postgres as liability
from test_financial_statement_snapshot_postgres import (
    isolated_statement_database as _isolated_statement_database,
)
from test_proven_source_composition_postgres import MIGRATION, _install, _rows
from test_retained_cutoff_assessment_postgres import (
    _backdated_collection,
    _exact,
    _post,
    _prepare,
    _seed,
)
from test_retained_cutoff_assessment_postgres import (
    cutoff_assessment as _cutoff_assessment,
)
from test_treasury_receipt_accounting_postgres import install

isolated_statement_database = _isolated_statement_database
cutoff_assessment = _cutoff_assessment


def _complete_cutoff(f):
    _install(f["conn"])
    conn = f["conn"]
    event = conn.execute(
        "SELECT id FROM lending.loan_disbursement_events WHERE loan_id=%s",
        (f["loan"],),
    ).fetchone()[0]
    rule = tax._record_rule(
        conn,
        actor_id=f["actor"],
        tax_type="documentary_stamp_tax",
        key="composition-" + f["suffix"],
        effective_from=f["cutoff"],
        rate="0.0075",
        maturity_max_days=None,
        digest_char="c",
    )
    evidence = conn.execute(
        "SELECT accounting.record_v1_dst_evidence(%s,%s,%s,%s,%s,5000.00,120,12.33,%s,%s,%s,%s,%s,NULL)",
        (
            f["actor"],
            uuid4(),
            f["loan"],
            event,
            rule,
            "Synthetic signed debt instrument",
            "d" * 64,
            "Synthetic retained tax calculation",
            "d" * 64,
            "Reviewed actual cutoff debt instrument and retained statutory tax calculation.",
        ),
    ).fetchone()[0]
    conn.execute(
        "SELECT accounting.prepare_v1_tax_liability_journal(%s,%s,%s)",
        ("documentary_stamp_tax", evidence, f["actor"]),
    )
    liability._post(
        conn,
        tax_type="documentary_stamp_tax",
        evidence_id=evidence,
        actor_id=f["actor"],
        evidence_digest="d" * 64,
        tax_due="12.33",
        expense_code="5310",
        posting_date=f["cutoff"],
        period_id=f["period"],
    )
    prepared, digest = _prepare(f)
    _post(f, prepared, digest)
    return f


def test_exact_proof_reaches_private_and_public_guards_with_unpaid_tax(
    cutoff_assessment,
):
    f = _complete_cutoff(cutoff_assessment)
    for public in (False, True):
        assert _rows(f, public) == []
    assert (
        f["conn"]
        .execute(
            "SELECT sum(l.credit-l.debit) FROM accounting.journal_lines l JOIN accounting.journal_entries j ON j.id=l.journal_entry_id JOIN accounting.accounts a ON a.id=l.account_id WHERE j.status='posted' AND a.code='2100'"
        )
        .fetchone()[0]
        > 0
    )
    f["conn"].execute(
        "SELECT accounting.assert_period_legacy_source_complete(%s),accounting.assert_period_source_complete(%s)",
        (f["period"], f["period"]),
    )
    close._move_to_review(f["conn"], f["period"], f["actor"])
    f["conn"].execute("SET CONSTRAINTS ALL IMMEDIATE")
    assert _exact(f)
    assert _rows(f, True) == []


def test_composition_replay_retains_raw_authority_and_existing_proof(cutoff_assessment):
    f = _complete_cutoff(cutoff_assessment)
    install(f["conn"], MIGRATION)
    assert _exact(f)
    assert _rows(f) == _rows(f, True) == []
    assert (
        f["conn"]
        .execute(
            "SELECT count(*) FROM accounting.period_legacy_uncomposed_source_blockers(%s) WHERE source_type IN ('eir_period_end','ecl_period_end')",
            (f["period"],),
        )
        .fetchone()[0]
        == 2
    )


def test_deferred_guard_rejects_later_source_in_review_transaction(cutoff_assessment):
    f = _complete_cutoff(cutoff_assessment)
    with pytest.raises(psycopg.Error, match="unreconciled"), f["conn"].transaction():
        close._move_to_review(f["conn"], f["period"], f["actor"])
        _backdated_collection(f)
        f["conn"].execute("SET CONSTRAINTS ALL IMMEDIATE")
    assert (
        f["conn"]
        .execute(
            "SELECT status FROM accounting.fiscal_periods WHERE id=%s", (f["period"],)
        )
        .fetchone()[0]
        == "open"
    )
    assert _exact(f)


@pytest.mark.parametrize("winner", ["source", "review"])
def test_composed_review_waits_and_rechecks_source_proof(
    isolated_statement_database, winner
):
    url = isolated_statement_database
    with psycopg.connect(url) as setup:
        case = _complete_cutoff(_seed(setup))
    waiter_started = Event()
    waiter_pid = []

    def waiting_operation():
        with psycopg.connect(url) as conn:
            conn.execute("SET statement_timeout='15s'")
            waiter_pid.append(conn.info.backend_pid)
            waiter_started.set()
            f = case | {"conn": conn}
            if winner == "source":
                close._move_to_review(conn, f["period"], f["actor"])
                return None
            return _backdated_collection(f)

    with (
        psycopg.connect(url) as first,
        psycopg.connect(url, autocommit=True) as observer,
        ThreadPoolExecutor(max_workers=1) as pool,
    ):
        first.execute("SET statement_timeout='15s'")
        f = case | {"conn": first}
        if winner == "source":
            first_result = _backdated_collection(f)
        else:
            close._move_to_review(first, f["period"], f["actor"])
            first_result = None
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
        assert blocked, "Close/source must wait on authoritative evidence locks"
        first.commit()
        if winner == "source":
            with pytest.raises(psycopg.Error, match="unreconciled"):
                future.result(timeout=15)
            source = first_result
        else:
            source = future.result(timeout=15)
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
            "SELECT status FROM accounting.fiscal_periods WHERE id=%s",
            (case["period"],),
        ).fetchone()[0] == ("open" if winner == "source" else "review")
        assert any(
            row["source_type"] == "eir_period_end"
            for row in _rows(case | {"conn": check}, True)
        )
