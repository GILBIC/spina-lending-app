"""Native origin admission must reach its real economic-date boundary.

These use the real current-day payout workflow, without a substituted clock or
legacy release journal. Positive elapsed historical cases require a retained
dated source fixture and are tested separately.
"""

# Imported fixtures are registered with pytest and referenced by argument name.
# ruff: noqa: F401, F811

import os
from pathlib import Path

import pytest
from test_native_payout_regular_origin_postgres import (
    _actual_debit,
    _assert_no_legacy_cash,
    _complete,
    native_origin,
    payout_accounting,
    payout_database,
    private_fixture_configuration,
)
from test_treasury_receipt_accounting_postgres import install

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "sql/0163_add_native_regular_assessment_integration.sql"
)


@pytest.fixture
def integrated_native(native_origin):
    f = native_origin
    if MIGRATION.exists() and os.getenv("SPINA_NATIVE_BASELINE") != "1":
        install(f["conn"], MIGRATION)
    f["conn"].execute(
        "UPDATE accounting.fiscal_periods SET end_date=%s WHERE id=%s",
        (f["today"], f["period"]),
    )
    f["conn"].commit()
    return f


def test_new_native_release_initializes_the_authoritative_contractual_collection_state(
    integrated_native,
):
    f = integrated_native
    prepared, _ = _actual_debit(f)
    _complete(f, prepared)
    state = (
        f["conn"]
        .execute(
            "SELECT remaining_balance,is_reconciled,state_version FROM lending.loan_collection_state WHERE loan_id=%s",
            (f["loan_id"],),
        )
        .fetchone()
    )
    total = (
        f["conn"]
        .execute(
            "SELECT sum(i.contractual_amount) AS amount FROM lending.first_loan_releases r "
            "JOIN lending.loan_contract_installments i ON i.schedule_id=r.schedule_id WHERE r.loan_id=%s",
            (f["loan_id"],),
        )
        .fetchone()["amount"]
    )
    assert state == {
        "remaining_balance": total,
        "is_reconciled": True,
        "state_version": 0,
    }


def candidate(f):
    return (
        f["conn"]
        .execute(
            "SELECT accounting.loan_period_elapsed_assessment_candidate(%s,%s) AS value",
            (f["period"], f["loan_id"]),
        )
        .fetchone()["value"]
    )


def test_elapsed_assessment_recognizes_native_completion_then_enforces_elapsed_date(
    integrated_native,
):
    f = integrated_native
    prepared, _ = _actual_debit(f)
    _complete(f, prepared)
    before = (
        f["conn"]
        .execute("SELECT count(*) AS n FROM accounting.journal_entries")
        .fetchone()["n"]
    )

    reviewed = candidate(f)

    assert not reviewed["ready"]
    assert "elapsed_original_contract_boundary_required" in reviewed["blockers"]
    assert "single_protected_regular_anchor_required" not in reviewed["blockers"]
    assert "release_cash_chart_meaning_mismatch" not in reviewed["blockers"]
    assert (
        f["conn"]
        .execute("SELECT count(*) AS n FROM accounting.journal_entries")
        .fetchone()["n"]
        == before
    )
    _assert_no_legacy_cash(f)


def test_elapsed_assessment_requires_native_borrower_completion(integrated_native):
    f = integrated_native
    _actual_debit(f)

    reviewed = candidate(f)

    assert not reviewed["ready"]
    assert "native_payout_completion_required" in reviewed["blockers"]
    assert "single_protected_regular_anchor_required" not in reviewed["blockers"]
    _assert_no_legacy_cash(f)


def test_elapsed_assessment_rechecks_exact_native_posting(integrated_native):
    f = integrated_native
    prepared, _ = _actual_debit(f)
    _complete(f, prepared)
    # A semantic role change invalidates retained source proof, even though the
    # original journal remains balanced and the native loan has been released.
    f["conn"].execute(
        "UPDATE accounting.accounts SET is_posting=false WHERE code='1100'"
    )

    reviewed = candidate(f)

    assert not reviewed["ready"]
    assert "native_payout_posting_not_exact" in reviewed["blockers"]
    _assert_no_legacy_cash(f)
