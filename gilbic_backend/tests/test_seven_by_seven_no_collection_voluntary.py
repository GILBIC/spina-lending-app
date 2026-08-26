from datetime import date
from decimal import Decimal

import pytest

from gilbic_backend.seven_by_seven_no_collection_voluntary import (
    NoCollectionAffectedInstallment,
    NoCollectionPastDueObligation,
    SevenBySevenNoCollectionExtraChoiceRequired,
    SevenBySevenNoCollectionVoluntaryError,
    plan_seven_by_seven_no_collection_voluntary_payment,
)


NC_DATE = date(2026, 8, 29)


def _past_due(number: int, day: int, remaining: str) -> NoCollectionPastDueObligation:
    return NoCollectionPastDueObligation(
        installment_id=number,
        installment_number=number,
        effective_due_date=date(2026, 8, day),
        remaining_amount=Decimal(remaining),
    )


def _affected(
    *,
    contractual: str = "50.00",
    prepaid: str = "0.00",
) -> NoCollectionAffectedInstallment:
    return NoCollectionAffectedInstallment(
        installment_id=99,
        installment_number=20,
        contractual_amount=Decimal(contractual),
        prepaid_amount=Decimal(prepaid),
    )


def test_old_past_due_consumes_cash_before_optional_no_collection_row() -> None:
    plan = plan_seven_by_seven_no_collection_voluntary_payment(
        transaction_amount="30.00",
        collection_date=NC_DATE,
        no_collection_date=NC_DATE,
        past_due_obligations=(_past_due(1, 28, "30.00"),),
        affected_installment=_affected(),
    )

    assert plan.status == "past_due_only"
    assert plan.past_due_cash_amount == Decimal("30.00")
    assert plan.affected_cash_amount == Decimal("0.00")
    assert plan.immediate_financial_cash_amount == Decimal("30.00")
    assert plan.keep_interest_holiday is True
    assert plan.keep_no_collection_shift is True
    assert [item.target for item in plan.instructions] == ["past_due"]


def test_remainder_below_affected_row_becomes_shifted_prepayment_without_interest() -> None:
    plan = plan_seven_by_seven_no_collection_voluntary_payment(
        transaction_amount="50.00",
        collection_date=NC_DATE,
        no_collection_date=NC_DATE,
        past_due_obligations=(_past_due(1, 28, "30.00"),),
        affected_installment=_affected(),
    )

    assert plan.status == "partial_shifted_prepayment"
    assert plan.past_due_cash_amount == Decimal("30.00")
    assert plan.affected_cash_amount == Decimal("20.00")
    assert plan.immediate_financial_cash_amount == Decimal("30.00")
    assert plan.shifted_prepayment_amount == Decimal("20.00")
    assert plan.keep_interest_holiday is True
    assert plan.keep_no_collection_shift is True
    assert [item.target for item in plan.instructions] == [
        "past_due",
        "affected_no_collection_installment",
    ]


def test_full_affected_row_after_past_due_marks_full_voluntary_exception() -> None:
    plan = plan_seven_by_seven_no_collection_voluntary_payment(
        transaction_amount="80.00",
        collection_date=NC_DATE,
        no_collection_date=NC_DATE,
        past_due_obligations=(_past_due(1, 28, "30.00"),),
        affected_installment=_affected(),
    )

    assert plan.status == "full_voluntary_completion"
    assert plan.past_due_cash_amount == Decimal("30.00")
    assert plan.affected_cash_amount == Decimal("50.00")
    assert plan.immediate_financial_cash_amount == Decimal("80.00")
    assert plan.shifted_prepayment_amount == Decimal("0.00")
    assert plan.prior_advance_activation_amount == Decimal("0.00")
    assert plan.keep_interest_holiday is False
    assert plan.keep_no_collection_shift is False


def test_finishing_partly_prepaid_row_identifies_prior_advance_for_original_date_activation() -> None:
    plan = plan_seven_by_seven_no_collection_voluntary_payment(
        transaction_amount="30.00",
        collection_date=NC_DATE,
        no_collection_date=NC_DATE,
        past_due_obligations=(),
        affected_installment=_affected(prepaid="20.00"),
    )

    assert plan.status == "full_voluntary_completion"
    assert plan.affected_prepaid_before == Decimal("20.00")
    assert plan.affected_cash_amount == Decimal("30.00")
    assert plan.affected_total_after == Decimal("50.00")
    assert plan.prior_advance_activation_amount == Decimal("20.00")
    assert plan.keep_interest_holiday is False
    assert plan.keep_no_collection_shift is False


def test_cash_beyond_past_due_and_affected_row_requires_explicit_extra_choice() -> None:
    with pytest.raises(
        SevenBySevenNoCollectionExtraChoiceRequired,
        match="Choose an eligible extra disposition",
    ):
        plan_seven_by_seven_no_collection_voluntary_payment(
            transaction_amount="81.00",
            collection_date=NC_DATE,
            no_collection_date=NC_DATE,
            past_due_obligations=(_past_due(1, 28, "30.00"),),
            affected_installment=_affected(),
        )


def test_already_fully_prepaid_affected_row_does_not_turn_new_cash_into_fake_completion() -> None:
    with pytest.raises(
        SevenBySevenNoCollectionExtraChoiceRequired,
        match="already fully prepaid",
    ):
        plan_seven_by_seven_no_collection_voluntary_payment(
            transaction_amount="10.00",
            collection_date=NC_DATE,
            no_collection_date=NC_DATE,
            past_due_obligations=(),
            affected_installment=_affected(prepaid="50.00"),
        )


def test_past_due_priority_is_chronological_even_if_input_is_not() -> None:
    plan = plan_seven_by_seven_no_collection_voluntary_payment(
        transaction_amount="35.00",
        collection_date=NC_DATE,
        no_collection_date=NC_DATE,
        past_due_obligations=(
            _past_due(2, 28, "20.00"),
            _past_due(1, 27, "20.00"),
        ),
        affected_installment=_affected(),
    )

    assert plan.status == "past_due_only"
    assert [(item.installment_number, item.amount_applied) for item in plan.instructions] == [
        (1, Decimal("20.00")),
        (2, Decimal("15.00")),
    ]
    assert plan.keep_interest_holiday is True


def test_planner_rejects_wrong_date_and_invalid_prepayment_evidence() -> None:
    with pytest.raises(SevenBySevenNoCollectionVoluntaryError, match="active No Collection date"):
        plan_seven_by_seven_no_collection_voluntary_payment(
            transaction_amount="50.00",
            collection_date=date(2026, 8, 30),
            no_collection_date=NC_DATE,
            past_due_obligations=(),
            affected_installment=_affected(),
        )

    with pytest.raises(SevenBySevenNoCollectionVoluntaryError, match="invalid prepayment"):
        plan_seven_by_seven_no_collection_voluntary_payment(
            transaction_amount="10.00",
            collection_date=NC_DATE,
            no_collection_date=NC_DATE,
            past_due_obligations=(),
            affected_installment=_affected(prepaid="50.01"),
        )
