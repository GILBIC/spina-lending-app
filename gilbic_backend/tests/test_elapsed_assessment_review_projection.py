"""Recovered preparation review uses exact retained inputs, never private snapshots."""

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from gilbic_backend.elapsed_period_assessment_repository import _prepared_payload


def test_retained_review_inputs_are_deep_allowlisted_and_decimal_exact():
    scope = UUID("00000000-0000-4000-8000-000000000001")
    row = {
        "id": scope,
        "book_id": scope,
        "fiscal_period_id": scope,
        "loan_id": scope,
        "as_of_date": date(2026, 9, 30),
        "calculated_at": datetime(2026, 10, 5, tzinfo=timezone.utc),
        "confirmation_digest": "a" * 64,
        "source_digest": "b" * 64,
        "source_snapshot": {
            "eir": {"incremental_interest": "1.00", "cumulative_interest": "2.00"},
            "private": "PRIVATE",
        },
        "measurement_snapshot": {
            "policy_version": "historical_original_timing_cash_shortfall_v1",
            "ecl_amount": "0.00",
            "prior_allowance": "0.00",
            "allowance_delta": "0.00",
            "scenarios": [{}, {}],
            "private": "PRIVATE",
        },
        "risk_review": {
            "as_of_date": "2026-09-30",
            "stage_label": "stage_1_12_month",
            "default_label": False,
            "write_off_label": "none",
            "recovery_label": "none",
            "primary_evidence_basis": "contractual_dpd",
            "evidence_reference": "Reference",
            "review_note": "Reviewed dated risk evidence.",
            "private": "PRIVATE",
        },
        "scenarios": [
            {
                "scenario_key": "base",
                "probability": Decimal("0.123456789012"),
                "evidence_reference": "Forecast",
                "management_rationale": "Reviewed dated forecast evidence.",
                "forward_evidence_ids": [str(scope)],
                "expected_cash_flows": [
                    {
                        "cash_date": "2026-10-20",
                        "amount": Decimal("1234567890123456.78"),
                        "private": "PRIVATE",
                    }
                ],
                "private": "PRIVATE",
            }
        ],
        "review_rationale": "Reviewed retained historical calculation.",
    }
    result = _prepared_payload(row)
    assert "review_inputs" in result
    review = result["review_inputs"]
    assert review["risk_review"]["as_of_date"] == "2026-09-30"
    assert review["scenarios"][0]["probability"] == "0.123456789012"
    assert (
        review["scenarios"][0]["expected_cash_flows"][0]["amount"]
        == "1234567890123456.78"
    )
    assert review["review_rationale"] == row["review_rationale"]
    assert "PRIVATE" not in repr(result)
