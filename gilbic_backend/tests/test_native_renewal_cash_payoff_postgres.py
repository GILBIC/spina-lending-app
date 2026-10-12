"""Actual renewed contract cash uses its retained active asset segment."""

# Imported fixtures are registered with pytest.
# ruff: noqa: F401, F811

from decimal import Decimal

import pytest
from test_native_regular_chronological_cash_postgres import post_application
from test_native_regular_historical_postgres import actual_first_application
from test_native_regular_payoff_postgres import (
    test_full_actual_payoff_posts_only_after_explicit_retained_contract_review as assert_payoff,
)
from test_native_renewal_lifecycle_postgres import (
    completed_native_renewal,
    dated_native,
    native_measurement_source,
    native_source,
)


@pytest.mark.parametrize(
    "treatment", ["modification_no_derecognition", "derecognition"]
)
def test_renewed_partial_cash_and_full_payoff_reconcile_active_segment(
    dated_native,
    monkeypatch,
    tmp_path,
    treatment,
):
    f = completed_native_renewal(
        dated_native, monkeypatch, tmp_path, treatment=treatment
    )
    conn = f["conn"]
    origin = conn.execute(
        "SELECT accounting.native_regular_segment_origin(%s,%s) AS source",
        (f["loan_id"], f["today"]),
    ).fetchone()["source"]
    assert origin["ready"], origin.get("blockers")
    rate = Decimal(str(origin["anchor"]["daily_eir"]))
    assert rate > 0
    first = actual_first_application(
        f,
        monkeypatch,
        tmp_path,
        amount_override=Decimal("50.00"),
        captured_reconciliation=False,
    )
    coordinates, journal = post_application(f, first)
    assert (
        coordinates["accounting_policy_version"]
        == "treasury_regular_renewal_chronological_cash_v1"
    )
    assert Decimal(str(coordinates["measurement"]["daily_eir"])) == rate
    assert Decimal(coordinates["measurement"]["incremental_interest"]) == 0
    conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
    conn.execute("SET CONSTRAINTS ALL DEFERRED")
    remaining = conn.execute(
        "SELECT remaining_balance FROM lending.loan_collection_state WHERE loan_id=%s",
        (f["loan_id"],),
    ).fetchone()["remaining_balance"]
    f["payoff"] = actual_first_application(
        f,
        monkeypatch,
        tmp_path,
        amount_override=remaining,
        captured_reconciliation=False,
    )
    assert_payoff(f)
    assert conn.execute(
        "SELECT exact_posted AND NOT correction_pending AS exact FROM accounting.treasury_application_posting_status WHERE journal_entry_id=%s",
        (journal,),
    ).fetchone()["exact"]
    assert conn.execute(
        "SELECT accounting.native_renewal_structural_exact(%s) AS exact",
        (f["journal_id"],),
    ).fetchone()["exact"]


def test_current_impaired_label_only_renewal_cash_has_no_net_opening(
    dated_native, monkeypatch, tmp_path
):
    f = completed_native_renewal(
        dated_native,
        monkeypatch,
        tmp_path,
        treatment="modification_no_derecognition",
        predecessor_credit_impaired=True,
    )
    first = actual_first_application(
        f,
        monkeypatch,
        tmp_path,
        amount_override=Decimal("50.00"),
        captured_reconciliation=False,
    )
    post_application(f, first)
    candidate = (
        f["conn"]
        .execute(
            "SELECT accounting.native_impaired_cash_candidate(%s,%s,%s) AS value",
            (f["application_period_id"], f["loan_id"], first["application_id"]),
        )
        .fetchone()["value"]
    )
    assert not candidate["ready"]
    assert candidate["blockers"] == ["posted_opening_impaired_assessment_required"]
