"""Current actual full payoff requires retained contract treatment evidence."""

# Imported fixtures are registered with pytest.
# ruff: noqa: F401, F811

import os
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from test_native_regular_chronological_cash_postgres import first_cash, post_application
from test_native_regular_historical_postgres import (
    actual_first_application,
    dated_native,
)
from test_treasury_receipt_accounting_postgres import install

MIGRATION = (
    Path(__file__).resolve().parents[1] / "sql/0167_add_regular_payoff_accounting.sql"
)


@pytest.fixture
def actual_payoff(first_cash, monkeypatch, tmp_path):
    f = first_cash
    if MIGRATION.exists() and os.getenv("SPINA_PAYOFF_BASELINE") != "1":
        install(f["conn"], MIGRATION)
    remaining = (
        f["conn"]
        .execute(
            "SELECT remaining_balance FROM lending.loan_collection_state WHERE loan_id=%s",
            (f["loan_id"],),
        )
        .fetchone()["remaining_balance"]
    )
    f["payoff"] = actual_first_application(
        f, monkeypatch, tmp_path, amount_override=remaining
    )
    return f


def test_full_actual_payoff_posts_only_after_explicit_retained_contract_review(
    actual_payoff,
):
    f = actual_payoff
    conn = f["conn"]
    with pytest.raises(psycopg.Error), conn.transaction():
        post_application(f, f["payoff"])
    source = conn.execute(
        "SELECT accounting.regular_payoff_candidate(%s) AS source",
        (f["payoff"]["application_id"],),
    ).fetchone()["source"]
    assert source["ready"], source["blockers"]
    reviewed = conn.execute(
        "SELECT accounting.record_regular_payoff_review(%s,%s,%s,%s,%s,%s,%s) AS id",
        (
            f["payoff"]["application_id"],
            source["source_digest"],
            uuid4(),
            "full_contractual_payoff_no_rebate",
            source["contract_evidence_reference"],
            "Synthetic explicit signed-contract settlement review confirms the complete contractual payoff without rebate.",
            f["actor_id"],
        ),
    ).fetchone()["id"]
    posted_source, journal = post_application(f, f["payoff"])
    assert (
        posted_source["accounting_policy_version"]
        == "treasury_regular_original_full_payoff_v1"
    )
    assert posted_source["measurement"]["payoff_review_id"] == str(reviewed)
    assert Decimal(posted_source["measurement"]["loan_component_after"]) == 0
    assert Decimal(posted_source["measurement"]["accrued_interest_after"]) == 0
    assert not {"1010", "1020", "1030", "1050"}.intersection(
        line["account_code"] for line in posted_source["lines"]
    )
    assert conn.execute(
        "SELECT exact_posted AND NOT correction_pending AS exact FROM accounting.treasury_application_posting_status WHERE journal_entry_id=%s",
        (journal,),
    ).fetchone()["exact"]
    cutoff = conn.execute(
        "SELECT accounting.loan_period_elapsed_assessment_candidate(%s,%s) AS source",
        (f["application_period_id"], f["loan_id"]),
    ).fetchone()["source"]
    assert cutoff["ready"], cutoff["blockers"]
    assert cutoff["snapshot"]["settled_by_exact_payoff"]
    assert Decimal(str(cutoff["snapshot"]["gross_carrying_amount"])) == 0
    assert Decimal(str(cutoff["snapshot"]["contractual_pv_raw"])) == 0
    risk = {
        "as_of_date": f["today"].isoformat(),
        "primary_evidence_basis": "exact_payoff",
        "evidence_reference": str(reviewed),
        "review_note": "Reviewed exact contractual payoff and the zero remaining exposure.",
    }
    from psycopg.types.json import Jsonb

    prepared = conn.execute(
        "SELECT accounting.prepare_elapsed_loan_period_assessment(%s,%s,%s,%s,%s,%s,%s) AS id",
        (
            f["application_period_id"],
            f["loan_id"],
            f["actor_id"],
            cutoff["source_digest"],
            Jsonb(risk),
            Jsonb([]),
            "Reviewed exact contractual payoff and the zero remaining exposure.",
        ),
    ).fetchone()["id"]
    assessment = conn.execute(
        "SELECT * FROM accounting.loan_elapsed_assessment_preparations WHERE id=%s",
        (prepared,),
    ).fetchone()
    assert Decimal(str(assessment["measurement_snapshot"]["ecl_amount"])) == 0
    conn.execute(
        "SELECT accounting.post_elapsed_loan_period_assessment(%s,%s,%s)",
        (prepared, f["actor_id"], assessment["confirmation_digest"]),
    )
    conn.execute("SET CONSTRAINTS ALL IMMEDIATE")


@pytest.mark.parametrize(
    "changed", ["digest", "contract", "actor", "rationale", "treatment"]
)
def test_payoff_review_rejects_unconfirmed_or_unrelated_evidence(
    actual_payoff, changed
):
    f = actual_payoff
    source = (
        f["conn"]
        .execute(
            "SELECT accounting.regular_payoff_candidate(%s) AS source",
            (f["payoff"]["application_id"],),
        )
        .fetchone()["source"]
    )
    values = [
        f["payoff"]["application_id"],
        source["source_digest"],
        uuid4(),
        "full_contractual_payoff_no_rebate",
        source["contract_evidence_reference"],
        "Explicit complete signed-contract payoff treatment review.",
        f["actor_id"],
    ]
    index, value = {
        "digest": (1, "0" * 64),
        "contract": (4, "unrelated-contract"),
        "actor": (6, uuid4()),
        "rationale": (5, "short"),
        "treatment": (3, "invented_rebate"),
    }[changed]
    values[index] = value
    with pytest.raises(psycopg.Error), f["conn"].transaction():
        f["conn"].execute(
            "SELECT accounting.record_regular_payoff_review(%s,%s,%s,%s,%s,%s,%s)",
            values,
        )
    assert (
        f["conn"]
        .execute("SELECT count(*) AS n FROM accounting.regular_payoff_reviews")
        .fetchone()["n"]
        == 0
    )
    assert (
        f["conn"]
        .execute(
            "SELECT count(*) AS n FROM accounting.treasury_application_postings WHERE application_id=%s",
            (f["payoff"]["application_id"],),
        )
        .fetchone()["n"]
        == 0
    )
