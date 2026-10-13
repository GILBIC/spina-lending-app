"""Actual-day review binding, exact retry, and current authority on native sources."""

# Imported fixtures are registered with pytest.
# ruff: noqa: F401, F811
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event
from time import monotonic, sleep
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from test_native_credit_risk_assessment_postgres import (
    _actual_debit,
    _complete,
    _schedule,
    actual_first_application,
    native_origin,
    native_risk,
    payout_accounting,
    payout_database,
    post_application,
    private_fixture_configuration,
    reviewed_stage,
    same_day_native,
)
from test_treasury_receipt_accounting_postgres import install

REVIEW = {
    "stage_label": "stage_2_lifetime",
    "default_label": False,
    "write_off_label": "none",
    "recovery_label": "none",
    "primary_evidence_basis": "verified_qualitative_credit_event",
    "evidence_reference": "SYNTHETIC-CURRENT-REVIEW",
    "review_note": "Actual current synthetic borrower evidence reviewed explicitly.",
    "sicr_backstop_rebutted": False,
    "default_backstop_rebutted": False,
    "rebuttal_evidence_reference": None,
    "rebuttal_note": None,
    "write_off_evidence_reference": None,
    "write_off_note": None,
    "recovery_transaction_id": None,
}


@pytest.fixture
def current_risk(native_risk):
    f = native_risk
    migration = (
        Path(__file__).resolve().parents[1]
        / "sql/0171_add_current_credit_risk_review.sql"
    )
    if migration.exists():
        install(f["conn"], migration)
    f["book_id"] = (
        f["conn"].execute("SELECT id FROM accounting.book_identity").fetchone()["id"]
    )
    return f


def context(f):
    return (
        f["conn"]
        .execute(
            "SELECT accounting.current_credit_risk_review_context(%s,%s) AS value",
            (f["period"], f["loan_id"]),
        )
        .fetchone()["value"]
    )


def retain(f, source, *, review=None, actor=None, book=None):
    return (
        f["conn"]
        .execute(
            "SELECT accounting.retain_current_credit_risk_review(%s,%s,%s,%s,%s,%s) AS id",
            (
                f["period"],
                f["loan_id"],
                book or f["book_id"],
                source["source_digest"],
                Jsonb(review or REVIEW),
                actor or f["actor_id"],
            ),
        )
        .fetchone()["id"]
    )


def test_current_review_uses_real_cutoff_and_exact_replay(current_risk):
    f = current_risk
    source = context(f)
    assert source["ready"], source["blockers"]
    assert source["as_of_date"] == f["today"].isoformat()
    first = retain(f, source)
    assert retain(f, source) == first
    assert context(f)["source_digest"] != source["source_digest"]
    with pytest.raises(psycopg.Error), f["conn"].transaction():
        retain(
            f,
            source,
            review=REVIEW
            | {"review_note": "Changed request must not replay the retained decision."},
        )
    stored = (
        f["conn"]
        .execute(
            "SELECT * FROM accounting.ecl_credit_risk_label_reviews WHERE id=%s",
            (first,),
        )
        .fetchone()
    )
    assert str(stored["snapshot_schedule_id"]) == source["schedule_id"]
    assert stored["snapshot_days_past_due"] == source["days_past_due"]
    assert stored["reviewer_user_id"] == f["actor_id"]
    assert (
        f["conn"]
        .execute(
            "SELECT count(*) AS n FROM accounting.current_credit_risk_review_bindings"
        )
        .fetchone()["n"]
        == 1
    )


def test_current_review_rechecks_authority_source_and_latest_decision(current_risk):
    f = current_risk
    source = context(f)
    for values in ({"actor": uuid4()}, {"book": uuid4()}):
        with pytest.raises(psycopg.Error), f["conn"].transaction():
            retain(f, source, **values)
    first = retain(f, source)
    newer = reviewed_stage(f, "stage_3_credit_impaired")
    assert newer != first
    with pytest.raises(psycopg.Error), f["conn"].transaction():
        retain(f, source)
    current = context(f)
    impaired = REVIEW | {
        "stage_label": "stage_3_credit_impaired",
        "default_label": True,
    }
    assert retain(f, current, review=impaired) != first
    with pytest.raises(psycopg.Error), f["conn"].transaction():
        f["conn"].execute(
            "UPDATE core.users SET status='inactive' WHERE id=%s", (f["actor_id"],)
        )
        retain(f, current, review=impaired)


def test_review_never_fabricates_historical_cutoff_or_accepts_client_facts(
    current_risk,
):
    f = current_risk
    source = context(f)
    for changed in ({"as_of_date": "2020-01-01"}, {"default_label": "false"}):
        with pytest.raises(psycopg.Error), f["conn"].transaction():
            retain(f, source, review=REVIEW | changed)
    with f["conn"].transaction(force_rollback=True):
        f["conn"].execute(
            "UPDATE accounting.fiscal_periods SET end_date=end_date+1 WHERE id=%s",
            (f["period"],),
        )
        assert not context(f)["ready"]
        with pytest.raises(psycopg.Error), f["conn"].transaction():
            retain(f, source)
    with f["conn"].transaction(force_rollback=True):
        f["conn"].execute(
            "UPDATE lending.loans SET legacy_loan_id='SYNTHETIC-CHANGED-SOURCE' WHERE id=%s",
            (f["loan_id"],),
        )
        assert context(f)["source_digest"] != source["source_digest"]
        with pytest.raises(psycopg.Error), f["conn"].transaction():
            retain(f, source)


@pytest.mark.parametrize("changed", ["loan", "authority"])
def test_current_review_rechecks_after_concurrent_source_or_authority_change(
    current_risk, changed
):
    f = current_risk
    source = context(f)
    f["conn"].commit()
    url = os.environ["GILBIC_TEST_DATABASE_URL"]
    started, waiting_pid = Event(), []

    def waiting():
        with psycopg.connect(url, row_factory=dict_row) as conn:
            waiting_pid.append(conn.info.backend_pid)
            started.set()
            return retain(f | {"conn": conn}, source)

    with (
        psycopg.connect(url) as first,
        psycopg.connect(url, autocommit=True) as observer,
        ThreadPoolExecutor(max_workers=1) as pool,
    ):
        if changed == "loan":
            first.execute(
                "UPDATE lending.loans SET legacy_loan_id='SYNTHETIC-CONCURRENT-CHANGE' WHERE id=%s",
                (f["loan_id"],),
            )
        else:
            first.execute(
                "UPDATE core.users SET status='inactive' WHERE id=%s",
                (f["actor_id"],),
            )
        future = pool.submit(waiting)
        try:
            assert started.wait(timeout=5)
            deadline = monotonic() + 4
            blocked = False
            while monotonic() < deadline:
                blocked = observer.execute(
                    "SELECT %s=ANY(pg_blocking_pids(%s))",
                    (first.info.backend_pid, waiting_pid[0]),
                ).fetchone()[0]
                if blocked:
                    break
                sleep(0.01)
            assert blocked, (
                "Risk review must wait for the actual source or authority writer"
            )
            first.commit()
            with pytest.raises(psycopg.Error) as error:
                future.result(timeout=15)
            assert error.value.sqlstate == ("55000" if changed == "loan" else "42501")
        finally:
            first.rollback()
    assert (
        f["conn"]
        .execute(
            "SELECT count(*) AS n FROM accounting.current_credit_risk_review_bindings"
        )
        .fetchone()["n"]
        == 0
    )
    assert (
        f["conn"]
        .execute(
            "SELECT count(*) AS n FROM accounting.ecl_credit_risk_label_reviews WHERE loan_id=%s",
            (f["loan_id"],),
        )
        .fetchone()["n"]
        == 0
    )


def test_identical_concurrent_current_reviews_retain_one_decision(current_risk):
    f = current_risk
    source = context(f)
    f["conn"].commit()
    url = os.environ["GILBIC_TEST_DATABASE_URL"]
    start = Barrier(2)

    def simultaneous():
        with psycopg.connect(url, row_factory=dict_row) as conn:
            start.wait(timeout=5)
            return retain(f | {"conn": conn}, source)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(simultaneous) for _ in range(2)]
        identities = [future.result(timeout=15) for future in futures]
    assert identities[0] == identities[1]
    assert (
        f["conn"]
        .execute(
            "SELECT count(*) AS n FROM accounting.current_credit_risk_review_bindings"
        )
        .fetchone()["n"]
        == 1
    )
    assert (
        f["conn"]
        .execute(
            "SELECT count(*) AS n FROM accounting.ecl_credit_risk_label_reviews WHERE loan_id=%s",
            (f["loan_id"],),
        )
        .fetchone()["n"]
        == 1
    )
