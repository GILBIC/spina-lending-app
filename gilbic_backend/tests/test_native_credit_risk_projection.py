"""Lifetime review responses bind retained labels without exposing source files."""

from datetime import date, datetime, timezone
from uuid import uuid4

from gilbic_backend.elapsed_period_assessment_repository import _prepared_payload
from test_elapsed_period_assessment_api import BODY


def test_lifetime_preparation_projects_exact_retained_review_identity():
    row = {key: uuid4() for key in ("id", "book_id", "fiscal_period_id", "loan_id")} | {
        "source_digest": "a" * 64,
        "confirmation_digest": "b" * 64,
        "as_of_date": date(2026, 10, 10),
        "calculated_at": datetime(2026, 10, 10, tzinfo=timezone.utc),
        "source_snapshot": {
            "eir": {"incremental_interest": "0.00", "cumulative_interest": "5.00"},
            "native_origin": {"storage_key": "PRIVATE"},
        },
        "measurement_snapshot": {
            "policy_version": "historical_native_lifetime_cash_shortfall_v1",
            "credit_risk_review_id": 17,
            "risk_review": {
                "stage_label": "stage_2_lifetime",
                "default_label": False,
                "private": "PRIVATE",
            },
            "loss_horizon": "lifetime",
            "loss_basis": "contractual_cash_shortfall",
            "ecl_amount": "90.00",
            "prior_allowance": "20.00",
            "allowance_delta": "70.00",
            "scenarios": [{}, {}],
        },
        "risk_review": {"credit_risk_review_id": 17},
        "scenarios": BODY["scenarios"],
        "review_rationale": BODY["review_rationale"],
    }
    result = _prepared_payload(row)
    assert result["credit_risk_review_id"] == 17
    assert result["stage_label"] == "stage_2_lifetime"
    assert result["default_label"] is False
    assert result["loss_horizon"] == "lifetime"
    assert set(result["review_inputs"]) == {
        "credit_risk_review_id",
        "scenarios",
        "review_rationale",
    }
    assert result["review_inputs"]["credit_risk_review_id"] == 17
    assert (
        result["review_inputs"]["scenarios"][0]["expected_cash_flows"][0]["amount"]
        == "9999999999999999.99"
    )
    assert "PRIVATE" not in repr(result)
