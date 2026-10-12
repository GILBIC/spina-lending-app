"""Positive aged Stage 3 cash/renewal proof; real dated capture is mandatory."""

# Imported fixtures are registered by pytest.
# ruff: noqa: F401, F811

from decimal import Decimal
from uuid import UUID

import pytest
import test_native_renewal_lifecycle_postgres as renewal
from gilbic_backend.current_credit_risk_review_repository import public_context
from gilbic_backend.elapsed_period_assessment_repository import (
    _impaired_cash_review_payload,
    _impaired_cash_source_payload,
)
from native_stage3_elapsed_support import (
    aged_stage3,
    emit_public,
    independent_interest,
    money,
    retained_cash_review,
    verify_opening,
)
from psycopg.types.json import Jsonb
from test_current_credit_risk_review_postgres import REVIEW
from test_native_credit_risk_assessment_postgres import lifetime_scenarios
from test_native_regular_chronological_cash_postgres import post_application
from test_native_regular_historical_postgres import actual_first_application


def ledger(conn, loan):
    return {
        row["code"]: row["balance"]
        for row in conn.execute(
            "SELECT a.code,sum(l.debit-l.credit) AS balance FROM accounting.journal_lines l JOIN accounting.journal_entries j ON j.id=l.journal_entry_id JOIN accounting.accounts a ON a.id=l.account_id WHERE j.status='posted' AND l.loan_id=%s GROUP BY a.code",
            (loan,),
        ).fetchall()
    }


@pytest.mark.parametrize("cure", [False, True])
def test_genuine_aged_cash_renewal_and_successor_assessment(
    aged_stage3, monkeypatch, tmp_path, cure
):
    f = aged_stage3
    conn = f["conn"]
    captured = f["capture"]["assessment"]
    gross = money(captured["source_snapshot"]["gross_carrying_amount"])
    allowance = money(captured["measurement_snapshot"]["ecl_amount"])
    rate = Decimal(str(captured["source_snapshot"]["eir"]["daily_eir"]))
    rounded_gross_interest, economic_unwind = independent_interest(
        gross, allowance, rate, (f["today"] - f["cutoff"]).days
    )
    expected_net_interest = rounded_gross_interest - economic_unwind
    assert rounded_gross_interest > 0 and economic_unwind > 0
    retained = {}

    def actual_cash(source, patch, destination):
        applied = actual_first_application(
            source,
            patch,
            destination,
            captured_reconciliation=False,
        )
        retained["application"] = applied
        return applied

    def post_and_review(source, application):
        coordinates, journal = post_application(source, {"application_id": application})
        # Protected cumulative GI remains the gross source; the independent
        # net-carrying calculation above is not changed to absorb its rounding.
        gross_interest = money(coordinates["measurement"]["incremental_interest"])
        assert gross_interest > 0
        retained["gross_interest"] = gross_interest
        assert (
            money(coordinates["measurement"]["gross_carrying_before"])
            == gross + gross_interest
        )
        assert (
            money(coordinates["measurement"]["loan_component_after"])
            + money(coordinates["measurement"]["accrued_interest_after"])
            == gross + gross_interest - retained["application"]["amount"]
        )
        period = UUID(coordinates["fiscal_period_id"])
        candidate, review, target = retained_cash_review(source, application, period)
        assert candidate["opening_assessment_id"] == str(f["assessment_id"])
        assert not candidate.get("opening_renewal_review_id")
        retained.update(
            candidate=candidate, review=review, target=target, cash_journal=journal
        )
        return coordinates, journal

    # Adapt only test orchestration. The captured opening is verified, never
    # reposted; cash/review/renewal commands still run against real protected SQL.
    with monkeypatch.context() as adapters:
        adapters.setattr(
            renewal, "private_copy", lambda destination: f["private_store"]
        )
        adapters.setattr(renewal, "post_prefix", verify_opening)
        adapters.setattr(renewal, "actual_first_application", actual_cash)
        adapters.setattr(renewal, "post_application", post_and_review)
        completed = renewal.completed_native_renewal(
            f, adapters, tmp_path, predecessor_credit_impaired=True
        )
    candidate = completed["candidate"]
    boundary = candidate["credit_impaired_boundary"]
    target = retained["target"]
    gross_interest = retained["gross_interest"]
    unwind = gross_interest - expected_net_interest
    delta = target - allowance - unwind
    assert delta != 0
    assert {key: money(value) for key, value in boundary.items()} == {
        "allowance_before": allowance,
        "allowance_unwind": unwind,
        "impairment_adjustment": delta,
        "allowance_after": target,
    }
    review = conn.execute(
        "SELECT * FROM accounting.native_renewal_measurement_reviews WHERE id=%s",
        (completed["renewal_review"]["id"],),
    ).fetchone()
    source = review["source_snapshot"]["boundary"]
    assert source["net_interest_established"] is True
    assert money(source["impairment_interest"]["net_interest"]) == expected_net_interest
    assert money(source["impairment_interest"]["currency_rounding_adjustment"]) == (
        gross_interest - rounded_gross_interest
    )
    assert source["impairment_interest"]["opening_assessment_id"] == str(
        f["assessment_id"]
    )
    assert (
        source["predecessor_risk_review"]["id"]
        == completed["predecessor_risk_review_id"]
    )
    assert any(
        item.get("id") == str(retained["review"]["id"])
        for item in source["impairment_interest"]["cash_measurements"]
    )
    lines = completed["completion"]["lines"]
    for component, expense, amount in (
        ("old_asset_allowance_unwind", "4000", unwind),
        ("old_asset_impaired_adjustment", "5000", delta),
    ):
        pair = [line for line in lines if line["component"] == component]
        assert len(pair) == 2 and {line["account_code"] for line in pair} == {
            expense,
            "1190",
        }
        assert all(line["loan_id"] == str(f["loan_id"]) for line in pair)
        assert sum(money(line["debit"]) - money(line["credit"]) for line in pair) == 0
        assert (
            next(
                money(line["debit"]) - money(line["credit"])
                for line in pair
                if line["account_code"] == expense
            )
            == amount
        )
    old_balances = ledger(conn, f["loan_id"])
    assert all(old_balances.get(code, 0) == 0 for code in ("1100", "1120", "1190"))
    assert ledger(conn, completed["loan_id"])["1190"] == -target
    # Receipt cash is recognized once; collection consumes its liability, and
    # renewal completion consumes funded transit without recognizing cash again.
    receipt_lines = conn.execute(
        "SELECT a.code,sum(l.debit-l.credit) AS amount FROM accounting.journal_lines l JOIN accounting.accounts a ON a.id=l.account_id WHERE l.journal_entry_id=%s GROUP BY a.code",
        (retained["application"]["receipt_journal_id"],),
    ).fetchall()
    receipt_amounts = {row["code"]: row["amount"] for row in receipt_lines}
    assert (
        sum(receipt_amounts.get(code, 0) for code in ("1010", "1020", "1030"))
        == retained["application"]["receipt_amount"]
    )
    assert not {"1010", "1020", "1030"}.intersection(
        line["account_code"] for line in lines
    )
    assert (
        sum(
            money(line["credit"]) - money(line["debit"])
            for line in lines
            if line["account_code"] == "1050"
        )
        == 1000
    )
    assert (
        conn.execute(
            "SELECT coalesce(sum(l.debit-l.credit),0) AS cash FROM accounting.journal_lines l JOIN accounting.accounts a ON a.id=l.account_id WHERE l.journal_entry_id=%s AND a.code IN('1010','1020','1030')",
            (retained["cash_journal"],),
        ).fetchone()["cash"]
        == 0
    )
    assert conn.execute(
        "SELECT accounting.native_renewal_structural_exact(%s) AS exact",
        (completed["journal_id"],),
    ).fetchone()["exact"]

    # Actual same-day successor cash starts after the protected renewal opening.
    applied = actual_first_application(
        completed,
        monkeypatch,
        tmp_path,
        amount_override=Decimal("50.00"),
        captured_reconciliation=False,
    )
    before_cash = ledger(conn, completed["loan_id"])
    cash_source, cash_journal = post_application(completed, applied)
    assert money(cash_source["measurement"]["incremental_interest"]) == 0
    after_cash = ledger(conn, completed["loan_id"])
    assert (
        sum(
            before_cash.get(code, 0) - after_cash.get(code, 0)
            for code in ("1100", "1120")
        )
        == 50
    )
    cash_candidate, cash_review, _ = retained_cash_review(
        completed, applied["application_id"], completed["application_period_id"]
    )
    assert cash_candidate["opening_assessment_id"] is None
    assert (
        cash_candidate["opening_renewal_review_id"] == completed["renewal_review"]["id"]
    )
    assert cash_candidate["opening_cutoff_date"] == f["today"].isoformat()
    assert conn.execute(
        "SELECT exact_posted AND NOT correction_pending AS exact FROM accounting.treasury_application_posting_status WHERE journal_entry_id=%s",
        (cash_journal,),
    ).fetchone()["exact"]

    context = conn.execute(
        "SELECT accounting.current_credit_risk_review_context(%s,%s) AS value",
        (completed["application_period_id"], completed["loan_id"]),
    ).fetchone()["value"]
    assert context["ready"] and context["prior_review"] is None
    assert context["inherited_review"]["loan_id"] == str(f["loan_id"])
    assert context["inherited_review"]["id"] == completed["predecessor_risk_review_id"]
    explicit = REVIEW | {
        "stage_label": "stage_1_12_month" if cure else "stage_3_credit_impaired",
        "default_label": not cure,
        "recovery_label": "cured" if cure else "none",
        "review_note": "Actual current objective borrower evidence explicitly supports the reviewed continuing asset risk state.",
    }
    args = (
        completed["application_period_id"],
        completed["loan_id"],
        UUID(candidate["book_id"]),
        context["source_digest"],
        Jsonb(explicit),
        f["actor_id"],
    )
    command = (
        "SELECT accounting.retain_current_credit_risk_review(%s,%s,%s,%s,%s,%s) AS id"
    )
    risk_id = conn.execute(command, args).fetchone()["id"]
    assert conn.execute(command, args).fetchone()["id"] == risk_id
    source = conn.execute(
        "SELECT accounting.loan_period_elapsed_assessment_candidate(%s,%s) AS value",
        (completed["application_period_id"], completed["loan_id"]),
    ).fetchone()["value"]
    assert source["ready"], source["blockers"]
    preparation = conn.execute(
        "SELECT accounting.prepare_elapsed_loan_risk_assessment(%s,%s,%s,%s,%s,%s,%s) AS id",
        (
            completed["application_period_id"],
            completed["loan_id"],
            f["actor_id"],
            source["source_digest"],
            risk_id,
            Jsonb(lifetime_scenarios(completed, source)),
            explicit["review_note"],
        ),
    ).fetchone()["id"]
    measured = conn.execute(
        "SELECT * FROM accounting.loan_elapsed_assessment_preparations WHERE id=%s",
        (preparation,),
    ).fetchone()
    interest = measured["measurement_snapshot"]["credit_impaired_interest"]
    assert interest["opening_assessment_id"] is None
    assert interest["opening_renewal_review_id"] == completed["renewal_review"]["id"]
    assert money(interest["allowance_unwind"]) == 0
    conn.execute(
        "SELECT accounting.post_elapsed_loan_period_assessment(%s,%s,%s)",
        (preparation, f["actor_id"], measured["confirmation_digest"]),
    )
    assert measured["measurement_snapshot"]["risk_review"]["recovery_label"] == (
        "cured" if cure else "none"
    )

    old = conn.execute(
        "SELECT accounting.loan_period_elapsed_assessment_candidate(%s,%s) AS value",
        (completed["application_period_id"], f["loan_id"]),
    ).fetchone()["value"]
    assert old["ready"], old["blockers"]
    old_risk = {
        "as_of_date": f["today"].isoformat(),
        "primary_evidence_basis": "exact_renewal",
        "evidence_reference": completed["renewal_review"]["id"],
        "review_note": "Exact completed renewal has zero predecessor exposure and cannot repeat impaired interest or loss.",
    }
    old_id = conn.execute(
        "SELECT accounting.prepare_elapsed_loan_period_assessment(%s,%s,%s,%s,%s,%s,%s) AS id",
        (
            completed["application_period_id"],
            f["loan_id"],
            f["actor_id"],
            old["source_digest"],
            Jsonb(old_risk),
            Jsonb([]),
            old_risk["review_note"],
        ),
    ).fetchone()["id"]
    old_row = conn.execute(
        "SELECT * FROM accounting.loan_elapsed_assessment_preparations WHERE id=%s",
        (old_id,),
    ).fetchone()
    assert (
        old_row["measurement_snapshot"]["ecl_amount"]
        == old_row["measurement_snapshot"]["allowance_delta"]
        == 0
    )
    assert "credit_impaired_interest" not in old_row["measurement_snapshot"]
    conn.execute(
        "SELECT accounting.post_elapsed_loan_period_assessment(%s,%s,%s)",
        (old_id, f["actor_id"], old_row["confirmation_digest"]),
    )
    assert conn.execute(
        "SELECT eir_journal_entry_id IS NULL AND allowance_journal_entry_id IS NULL AS no_repeat FROM accounting.loan_elapsed_assessment_postings WHERE preparation_id=%s",
        (old_id,),
    ).fetchone()["no_repeat"]
    assert conn.execute(
        "SELECT accounting.period_elapsed_loan_assessment_exact(%s,%s) AS exact",
        (f["period_id"], f["loan_id"]),
    ).fetchone()["exact"]
    conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
    emit_public(
        f"native-stage3-aged-{'cure' if cure else 'continuing'}.json",
        {
            "candidate": candidate,
            "completion": completed["completion"],
            "inherited_risk_context": public_context(context),
            "successor_cash_candidate": _impaired_cash_source_payload(cash_candidate),
            "successor_cash_review": _impaired_cash_review_payload(cash_review),
            "independent": {
                "gross_interest": gross_interest,
                "allowance_unwind": unwind,
                "impairment_adjustment": delta,
                "allowance_after": target,
            },
        },
    )
