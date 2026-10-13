"""Unsupported payout transit stays visible under every allowed chart change."""

import psycopg
import pytest
from test_first_loan_postgres import (
    private_fixture_configuration as _private_fixture_configuration,
)
from test_loan_payout_accounting_postgres import payout_accounting as _payout_accounting
from test_loan_payout_accounting_postgres import payout_database as _payout_database
from test_treasury_transfer_control_identity_postgres import manual_transit

payout_accounting = _payout_accounting
payout_database = _payout_database
private_fixture_configuration = _private_fixture_configuration


@pytest.mark.parametrize(
    "change",
    [
        "code='1098'",
        "system_key='recoded_transit'",
        "account_type='expense'",
        "normal_balance='credit'",
        "is_posting=false",
    ],
)
def test_unregistered_payout_transit_cannot_be_hidden_by_chart_change(
    payout_accounting, change
):
    f = payout_accounting
    journal = manual_transit(f, "1050")
    with (
        pytest.raises(psycopg.Error, match="control.*definition|immutable"),
        f["conn"].transaction(),
    ):
        f["conn"].execute(
            "UPDATE accounting.accounts SET " + change + " WHERE code='1050'"
        )
    assert (
        f["conn"]
        .execute(
            "SELECT amount FROM accounting.period_loan_payout_control_blockers(%s) WHERE source_id=%s",
            (f["period"], journal),
        )
        .fetchone()["amount"]
        == 100
    )


def test_unused_payout_transit_control_cannot_be_deleted(payout_accounting):
    with (
        pytest.raises(psycopg.Error, match="control.*definition|immutable"),
        payout_accounting["conn"].transaction(),
    ):
        payout_accounting["conn"].execute(
            "DELETE FROM accounting.accounts WHERE code='1050'"
        )


def test_payout_transit_display_change_preserves_unregistered_balance(
    payout_accounting,
):
    f = payout_accounting
    journal = manual_transit(f, "1050")
    f["conn"].execute(
        "UPDATE accounting.accounts SET is_active=false,name='Retired synthetic payout transit' WHERE code='1050'"
    )
    assert (
        f["conn"]
        .execute(
            "SELECT amount FROM accounting.period_loan_payout_control_blockers(%s) WHERE source_id=%s",
            (f["period"], journal),
        )
        .fetchone()["amount"]
        == 100
    )
