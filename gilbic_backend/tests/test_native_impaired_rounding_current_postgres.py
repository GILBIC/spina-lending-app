"""Run the independent currency examples against the final installed schema.

The historical suite additionally exercises a real protected cash source. These
pure numeric probes need no retained aged manifest and make no aged-posting claim.
"""

# Imported tests and their fixture dependencies are collected by pytest.
# ruff: noqa: F401, F811

import pytest
from test_native_impaired_cash_review_postgres import (
    impaired_cash,
    native_origin,
    native_risk,
    payout_accounting,
    payout_database,
    private_fixture_configuration,
    same_day_native,
)
from test_native_impaired_interest_rounding_postgres import (
    test_installed_chain_carries_reviewed_target_into_next_net_interval,
    test_installed_chain_rounds_net_basis_at_each_cash_boundary,
    test_installed_chain_uses_verified_gross_but_independent_net_interest,
    test_installed_no_cash_interest_uses_the_same_rounded_net_basis,
    test_legitimate_cumulative_rounding_can_have_signed_reconciliation,
    test_signed_reconciliation_journal_legs_and_renewal_conserve_allowance,
)


@pytest.fixture
def dated_native(impaired_cash):
    """Only the connection is used by the imported arithmetic examples."""
    return impaired_cash
