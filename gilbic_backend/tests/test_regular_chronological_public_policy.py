import pytest
from gilbic_backend.treasury_application_accounting_repository import (
    public_application_review,
)


@pytest.mark.parametrize(
    "policy",
    [
        "treasury_regular_original_chronological_cash_v1",
        "treasury_regular_renewal_chronological_cash_v1",
    ],
)
def test_later_regular_cash_review_keeps_product_policy_and_hides_prior_wallet_history(
    policy,
):
    source = {
        "product_model": "fixed_daily",
        "accounting_policy_version": policy,
        "application_id": "current-authorized-application",
        "source_digest": "a" * 64,
        "origin": {
            "cash_rollforward": {
                "cash_claims": [{"private_wallet_id": "another-wallet"}]
            }
        },
        "measurement": {"prior_recognized_interest": "10.00"},
        "lines": [
            {
                "line_number": 10,
                "account_code": "2200",
                "debit": "50.00",
                "credit": "0.00",
                "account_snapshot": {
                    "name": "Unapplied Borrower Funds",
                    "private_internal_id": "excluded",
                },
            },
            {
                "line_number": 50,
                "account_code": "1100",
                "debit": "0.00",
                "credit": "50.00",
                "account_snapshot": {"name": "Regular Loan Receivable"},
            },
        ],
    }
    result = public_application_review(source)
    assert result["product_model"] == "fixed_daily"
    assert result["accounting_policy_version"] == source["accounting_policy_version"]
    assert result["source_digest"] == source["source_digest"]
    assert "origin" not in result and "measurement" not in result
    assert "another-wallet" not in str(result)
    assert result["lines"][0]["account_snapshot"] == {
        "name": "Unapplied Borrower Funds"
    }
