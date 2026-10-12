"""A genuine dated origin must support ordinary subsequent actual cash."""

# Imported pytest fixtures are registered and referenced by argument name.
# ruff: noqa: F401, F811

import os
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from test_native_regular_historical_postgres import (
    actual_first_application,
    dated_native,
    post_prefix,
)
from test_treasury_receipt_accounting_postgres import install

MIGRATION = (
    Path(__file__).resolve().parents[1] / "sql/0165_add_regular_chronological_cash.sql"
)


def post_application(f, applied):
    conn = f["conn"]
    source = conn.execute(
        "SELECT accounting.treasury_application_coordinates(%s) AS source",
        (applied["application_id"],),
    ).fetchone()["source"]
    preparation = conn.execute(
        "SELECT accounting.prepare_treasury_application(%s,%s,%s,%s) AS id",
        (applied["application_id"], source["source_digest"], uuid4(), f["actor_id"]),
    ).fetchone()["id"]
    retained = conn.execute(
        "SELECT * FROM accounting.treasury_application_preparations WHERE id=%s",
        (preparation,),
    ).fetchone()
    journal = conn.execute(
        "SELECT accounting.post_treasury_application(%s,%s,%s,%s) AS id",
        (
            preparation,
            retained["source_digest"],
            retained["confirmation_token"],
            f["actor_id"],
        ),
    ).fetchone()["id"]
    return source, journal


@pytest.fixture
def first_cash(dated_native, monkeypatch, tmp_path):
    f = dated_native
    if MIGRATION.exists() and os.getenv("SPINA_CHRONOLOGICAL_BASELINE") != "1":
        install(f["conn"], MIGRATION)
    post_prefix(f)
    f["application_period_id"] = (
        f["conn"]
        .execute(
            "INSERT INTO accounting.fiscal_periods(label,start_date,end_date,status) "
            "VALUES(%s,%s,%s,'open') RETURNING id",
            (
                "Actual chronological cash " + uuid4().hex,
                f["cutoff"] + timedelta(days=1),
                f["today"],
            ),
        )
        .fetchone()["id"]
    )
    f["first_application"] = actual_first_application(f, monkeypatch, tmp_path)
    f["first_source"], f["first_journal"] = post_application(f, f["first_application"])
    return f


def test_second_actual_same_day_cash_keeps_first_source_exact(
    first_cash, monkeypatch, tmp_path
):
    f = first_cash
    second = actual_first_application(
        f, monkeypatch, tmp_path, amount_override=Decimal("50.00")
    )
    source, journal = post_application(f, second)
    assert Decimal(source["measurement"]["incremental_interest"]) == 0
    assert Decimal(source["measurement"]["cash_to_loan_component"]) == Decimal("50.00")
    assert not {"1010", "1020", "1030", "1050"}.intersection(
        line["account_code"] for line in source["lines"]
    )
    rows = (
        f["conn"]
        .execute(
            "SELECT exact_posted,correction_pending FROM accounting.treasury_application_posting_status "
            "WHERE journal_entry_id=ANY(%s)",
            ([journal, f["first_journal"]],),
        )
        .fetchall()
    )
    assert len(rows) == 2 and all(
        row["exact_posted"] and not row["correction_pending"] for row in rows
    )
    f["conn"].execute("SET CONSTRAINTS ALL IMMEDIATE")


def test_actual_cash_cutoff_uses_remaining_contract_and_posted_carrying(first_cash):
    f = first_cash
    source = (
        f["conn"]
        .execute(
            "SELECT accounting.loan_period_elapsed_assessment_candidate(%s,%s) AS source",
            (f["application_period_id"], f["loan_id"]),
        )
        .fetchone()["source"]
    )
    assert source["ready"], source["blockers"]
    assert Decimal(str(source["eir"]["incremental_interest"])) == 0
    assert Decimal(str(source["snapshot"]["gross_carrying_amount"])) == (
        Decimal(f["first_source"]["measurement"]["loan_component_after"])
        + Decimal(f["first_source"]["measurement"]["accrued_interest_after"])
    )
    assert (
        sum(
            Decimal(str(flow["allocated_amount"]))
            for flow in source["snapshot"]["contractual_cash_flows"]
        )
        == f["first_application"]["amount"]
    )


def test_later_cash_cannot_skip_a_real_unposted_payment(
    first_cash, monkeypatch, tmp_path
):
    f = first_cash
    second = actual_first_application(
        f, monkeypatch, tmp_path, amount_override=Decimal("50.00")
    )
    third = actual_first_application(
        f, monkeypatch, tmp_path, amount_override=Decimal("50.00")
    )
    with (
        pytest.raises(psycopg.Error, match="Exact chronological original cash claims"),
        f["conn"].transaction(),
    ):
        post_application(f, third)
    candidate = (
        f["conn"]
        .execute(
            "SELECT accounting.loan_period_elapsed_assessment_candidate(%s,%s) AS source",
            (f["application_period_id"], f["loan_id"]),
        )
        .fetchone()["source"]
    )
    assert not candidate["ready"]
    assert "prior_original_cash_posting_not_exact" in candidate["blockers"]
    assert (
        f["conn"]
        .execute(
            "SELECT count(*) AS n FROM accounting.treasury_application_postings WHERE application_id=ANY(%s)",
            ([second["application_id"], third["application_id"]],),
        )
        .fetchone()["n"]
        == 0
    )


def test_later_cash_rejects_changed_original_account_meaning(
    first_cash, monkeypatch, tmp_path
):
    f = first_cash
    second = actual_first_application(
        f, monkeypatch, tmp_path, amount_override=Decimal("50.00")
    )
    f["conn"].execute(
        "UPDATE accounting.accounts SET is_posting=false WHERE code='1100'"
    )
    with (
        pytest.raises(psycopg.Error, match="Exact chronological original cash claims"),
        f["conn"].transaction(),
    ):
        post_application(f, second)
    assert (
        f["conn"]
        .execute(
            "SELECT count(*) AS n FROM accounting.treasury_application_postings WHERE application_id=%s",
            (second["application_id"],),
        )
        .fetchone()["n"]
        == 0
    )


def test_chronological_audit_failure_rolls_back_the_new_journal(
    first_cash, monkeypatch, tmp_path
):
    f = first_cash
    second = actual_first_application(
        f, monkeypatch, tmp_path, amount_override=Decimal("50.00")
    )
    f["conn"].execute(
        "CREATE FUNCTION accounting.reject_synthetic_chronological_audit() RETURNS trigger LANGUAGE plpgsql AS $$ "
        "BEGIN RAISE EXCEPTION 'Synthetic chronological audit failure'; END $$"
    )
    f["conn"].execute(
        "CREATE TRIGGER reject_synthetic_chronological_audit BEFORE INSERT ON accounting.treasury_application_postings "
        "FOR EACH ROW EXECUTE FUNCTION accounting.reject_synthetic_chronological_audit()"
    )
    with (
        pytest.raises(psycopg.Error, match="Synthetic chronological audit failure"),
        f["conn"].transaction(),
    ):
        post_application(f, second)
    assert (
        f["conn"]
        .execute(
            "SELECT count(*) AS n FROM accounting.journal_entries WHERE source_event_key=%s",
            ("treasury_application:" + str(second["application_id"]),),
        )
        .fetchone()["n"]
        == 0
    )
    assert (
        f["conn"]
        .execute(
            "SELECT exact_posted AND NOT correction_pending AS exact FROM accounting.treasury_application_posting_status WHERE journal_entry_id=%s",
            (f["first_journal"],),
        )
        .fetchone()["exact"]
    )


def test_twenty_actual_payments_do_not_recursively_revalidate_every_prefix(
    first_cash, monkeypatch, tmp_path
):
    f = first_cash
    # A bounded statement, not a substituted clock or an unbounded benchmark.
    f["conn"].execute("SET LOCAL statement_timeout='5s'")
    f["conn"].execute("SET CONSTRAINTS ALL IMMEDIATE")
    f["conn"].execute("SET CONSTRAINTS ALL DEFERRED")
    for _ in range(20):
        applied = actual_first_application(
            f, monkeypatch, tmp_path, amount_override=Decimal("1.00")
        )
        source, _ = post_application(f, applied)
        assert Decimal(source["measurement"]["incremental_interest"]) == 0
        # Each real API operation commits before the next payment. Flush that
        # operation's deferred source guards within the same bounded statement.
        f["conn"].execute("SET CONSTRAINTS ALL IMMEDIATE")
        f["conn"].execute("SET CONSTRAINTS ALL DEFERRED")
    assert (
        f["conn"]
        .execute(
            "SELECT count(*) AS n FROM accounting.treasury_application_postings WHERE loan_id=%s",
            (f["loan_id"],),
        )
        .fetchone()["n"]
        == 21
    )
    f["conn"].execute("SET CONSTRAINTS ALL IMMEDIATE")
