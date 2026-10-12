"""A fresh retained proof cannot approve a misclassified control chart."""

import pytest
from test_retained_cutoff_assessment_postgres import (
    _candidate,
)
from test_retained_cutoff_assessment_postgres import (
    cutoff_assessment as _cutoff_assessment,
)

cutoff_assessment = _cutoff_assessment


@pytest.mark.parametrize(
    "key,account_type,normal_balance",
    [
        ("loans_receivable_regular", "liability", "credit"),
        ("loans_receivable_7x7", "asset", "credit"),
        ("accrued_interest_receivable", "asset", "credit"),
        ("allowance_expected_credit_loss", "asset", "debit"),
        ("credit_loss_expense", "liability", "credit"),
        ("cash_office", "liability", "credit"),
    ],
)
def test_fresh_assessment_rejects_changed_chart_meaning(
    cutoff_assessment, key, account_type, normal_balance
):
    f = cutoff_assessment
    assert _candidate(f)["ready"]
    result = (
        f["conn"]
        .execute(
            "UPDATE accounting.accounts SET account_type=%s,normal_balance=%s WHERE system_key=%s RETURNING id",
            (account_type, normal_balance, key),
        )
        .fetchone()
    )
    assert result is not None, "The regression must modify an actual chart account"
    candidate = _candidate(f)
    assert not candidate["ready"], candidate


def test_historical_control_retirement_does_not_change_chart_meaning(cutoff_assessment):
    f = cutoff_assessment
    f["conn"].execute(
        "UPDATE accounting.accounts SET name='Historical retained receivable',is_active=false,is_posting=false WHERE system_key='loans_receivable_regular'"
    )
    candidate = _candidate(f)
    assert candidate["ready"], candidate["blockers"]
