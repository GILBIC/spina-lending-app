from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from gilbic_backend.seven_by_seven_advance_activation import (
    SevenBySevenAdvanceFinancialReplay,
)
from gilbic_backend.seven_by_seven_no_collection_voluntary import (
    NoCollectionAffectedInstallment,
    plan_seven_by_seven_no_collection_voluntary_payment,
)
from gilbic_backend.seven_by_seven_no_collection_voluntary_financial import (
    SevenBySevenNoCollectionVoluntaryFinancialError,
    project_no_collection_voluntary_financial_state,
)
from gilbic_backend.seven_by_seven_operational_allocator import (
    SevenBySevenCashEvent,
    allocate_seven_by_seven_payments,
)


PAYMENT_START = date(2097, 8, 9)
NC_DATE = date(2097, 8, 10)
PRINCIPAL = Decimal("1000.00")
RATE = Decimal("7.00")


def _baseline(
    *,
    events: tuple[SevenBySevenCashEvent, ...] = (),
) -> SevenBySevenAdvanceFinancialReplay:
    result = allocate_seven_by_seven_payments(
        original_principal=PRINCIPAL,
        daily_interest_per_1000=RATE,
        payment_start=PAYMENT_START,
        events=events,
        interest_holiday_dates=(NC_DATE,),
    )
    return SevenBySevenAdvanceFinancialReplay(
        historical_events=events,
        result=result,
        matured_advance_row_count=0,
        interest_holiday_dates=(NC_DATE,),
    )


def _plan(*, receipt: str, prepaid: str):
    return plan_seven_by_seven_no_collection_voluntary_payment(
        transaction_amount=Decimal(receipt),
        collection_date=NC_DATE,
        no_collection_date=NC_DATE,
        past_due_obligations=(),
        affected_installment=NoCollectionAffectedInstallment(
            installment_id=20,
            installment_number=20,
            contractual_amount=Decimal("50.00"),
            prepaid_amount=Decimal(prepaid),
        ),
    )


def test_partial_affected_cash_remains_financially_deferred() -> None:
    baseline = _baseline()
    plan = _plan(receipt="20.00", prepaid="0.00")

    projection = project_no_collection_voluntary_financial_state(
        baseline=baseline,
        plan=plan,
        collection_date=NC_DATE,
        original_principal=PRINCIPAL,
        daily_interest_per_1000=RATE,
        payment_start=PAYMENT_START,
        previous_balance=PRINCIPAL,
        affected_installment_id=20,
        affected_deferred_prepaid_amount=Decimal("0.00"),
        pending_event_id="pending-partial",
    )

    assert plan.status == "partial_shifted_prepayment"
    assert plan.immediate_financial_cash_amount == Decimal("0.00")
    assert projection.pending_line is None
    assert projection.result.closing_remaining_principal == PRINCIPAL


def test_full_completion_activates_only_prior_deferred_evidence() -> None:
    baseline = _baseline()
    plan = _plan(receipt="30.00", prepaid="20.00")

    projection = project_no_collection_voluntary_financial_state(
        baseline=baseline,
        plan=plan,
        collection_date=NC_DATE,
        original_principal=PRINCIPAL,
        daily_interest_per_1000=RATE,
        payment_start=PAYMENT_START,
        previous_balance=PRINCIPAL,
        affected_installment_id=20,
        affected_deferred_prepaid_amount=Decimal("20.00"),
        pending_event_id="pending-full",
    )

    assert plan.status == "full_voluntary_completion"
    assert projection.pending_line is not None
    assert projection.result.closing_remaining_principal == Decimal("964.00")
    assert projection.pending_line.closing_remaining_principal == Decimal("964.00")


def test_full_completion_does_not_double_count_prior_cash_already_financially_active() -> None:
    prior = SevenBySevenCashEvent(
        event_id="prior-normal-payment",
        collection_date=NC_DATE,
        amount=Decimal("20.00"),
    )
    baseline = _baseline(events=(prior,))
    plan = _plan(receipt="30.00", prepaid="20.00")

    projection = project_no_collection_voluntary_financial_state(
        baseline=baseline,
        plan=plan,
        collection_date=NC_DATE,
        original_principal=PRINCIPAL,
        daily_interest_per_1000=RATE,
        payment_start=PAYMENT_START,
        previous_balance=baseline.result.closing_remaining_principal,
        affected_installment_id=20,
        affected_deferred_prepaid_amount=Decimal("0.00"),
        pending_event_id="pending-after-prior-normal",
    )

    assert baseline.result.closing_remaining_principal == Decimal("987.00")
    assert projection.result.closing_remaining_principal == Decimal("964.00")


def test_projection_rejects_deferred_evidence_above_total_prior_payment() -> None:
    baseline = _baseline()
    plan = _plan(receipt="30.00", prepaid="20.00")

    with pytest.raises(
        SevenBySevenNoCollectionVoluntaryFinancialError,
        match="does not reconcile",
    ):
        project_no_collection_voluntary_financial_state(
            baseline=baseline,
            plan=plan,
            collection_date=NC_DATE,
            original_principal=PRINCIPAL,
            daily_interest_per_1000=RATE,
            payment_start=PAYMENT_START,
            previous_balance=PRINCIPAL,
            affected_installment_id=20,
            affected_deferred_prepaid_amount=Decimal("20.01"),
            pending_event_id="pending-invalid",
        )
