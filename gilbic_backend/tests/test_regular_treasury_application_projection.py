"""Public application identity selects one complete product policy."""

import pytest
from gilbic_backend.treasury_application_accounting_repository import (
    public_application_review,
)
from gilbic_backend.treasury_authorization import TreasuryUnavailable


@pytest.mark.parametrize(
    "retained,model,policy",
    [
        ({}, "seven_by_seven", "treasury_seven_by_seven_application_v1"),
        (
            {
                "product_model": "fixed_daily",
                "accounting_policy_version": "treasury_regular_original_first_cash_v1",
            },
            "fixed_daily",
            "treasury_regular_original_first_cash_v1",
        ),
    ],
)
def test_public_application_carries_exact_product_policy_without_private_prefixes(
    retained, model, policy
):
    result = public_application_review(
        retained
        | {
            "lines": [],
            "prefix_claims": [{"private_source": "PRIVATE"}],
            "measurement": {"private_origin": "PRIVATE"},
        }
    )
    assert result["product_model"] == model
    assert result["accounting_policy_version"] == policy
    assert "prefix_claims" not in result and "measurement" not in result


@pytest.mark.parametrize(
    "retained",
    [
        {"product_model": "fixed_daily"},
        {"accounting_policy_version": "treasury_regular_original_first_cash_v1"},
        {
            "product_model": "seven_by_seven",
            "accounting_policy_version": "treasury_regular_original_first_cash_v1",
        },
        {"product_model": "unknown", "accounting_policy_version": "unknown"},
    ],
)
def test_unknown_or_mixed_product_policy_does_not_receive_a_public_review(retained):
    with pytest.raises(TreasuryUnavailable, match="policy"):
        public_application_review(retained | {"lines": []})
