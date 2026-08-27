from datetime import date, timedelta
from decimal import Decimal

import pytest

from gilbic_backend.seven_by_seven_extra_principal import (
    FutureInstallmentPrincipalState,
    SevenBySevenExtraPrincipalError,
    plan_seven_by_seven_extra_principal_tail,
)


def _row(
    number: int,
    *,
    principal: str = "29.00",
    interest: str = "21.00",
    advance: str = "0.00",
    signed_principal: str | None = None,
    signed_interest: str | None = None,
) -> FutureInstallmentPrincipalState:
    principal_amount = Decimal(principal)
    interest_amount = Decimal(interest)
    signed_principal_amount = (
        Decimal(signed_principal) if signed_principal is not None else None
    )
    signed_interest_amount = Decimal(signed_interest) if signed_interest is not None else None
    signed_contractual_amount = (
        signed_principal_amount + signed_interest_amount
        if signed_principal_amount is not None and signed_interest_amount is not None
        else None
    )
    return FutureInstallmentPrincipalState(
        installment_id=100 + number,
        installment_number=number,
        effective_due_date=date(2026, 9, 1) + timedelta(days=number - 1),
        contractual_amount=principal_amount + interest_amount,
        principal_component=principal_amount,
        interest_component=interest_amount,
        advance_allocated=Decimal(advance),
        signed_contractual_amount=signed_contractual_amount,
        signed_principal_component=signed_principal_amount,
        signed_interest_component=signed_interest_amount,
    )


def test_extra_principal_shortens_7x7_from_tail_without_rewriting_signed_amounts() -> None:
    plan = plan_seven_by_seven_extra_principal_tail(
        principal_reduction=Decimal("40.00"),
        future_installments=(_row(1), _row(2), _row(3)),
    )

    assert plan.prior_future_principal == Decimal("87.00")
    assert plan.resulting_future_principal == Decimal("47.00")
    assert plan.removed_future_interest == Decimal("21.00")
    assert plan.removed_installment_ids == (103,)

    first, boundary, removed = plan.installments
    assert first.signed_contractual_amount == Decimal("50.00")
    assert first.prior_operational_amount == Decimal("50.00")
    assert first.operational_amount == Decimal("50.00")
    assert first.operational_principal_component == Decimal("29.00")

    assert boundary.signed_contractual_amount == Decimal("50.00")
    assert boundary.signed_principal_component == Decimal("29.00")
    assert boundary.prior_operational_principal_component == Decimal("29.00")
    assert boundary.operational_principal_component == Decimal("18.00")
    assert boundary.operational_amount == Decimal("39.00")
    assert not boundary.removed_from_operational_schedule

    assert removed.signed_contractual_amount == Decimal("50.00")
    assert removed.operational_amount == Decimal("0.00")
    assert removed.operational_principal_component == Decimal("0.00")
    assert removed.removed_from_operational_schedule


def test_advance_on_fully_removed_tail_row_becomes_refund_due() -> None:
    plan = plan_seven_by_seven_extra_principal_tail(
        principal_reduction=Decimal("29.00"),
        future_installments=(_row(1), _row(2), _row(3, advance="25.00")),
    )

    assert plan.resulting_future_principal == Decimal("58.00")
    assert plan.advance_refund_due == Decimal("25.00")
    assert plan.removed_future_interest == Decimal("21.00")
    assert plan.installments[-1].advance_allocated == Decimal("25.00")
    assert plan.installments[-1].advance_retained == Decimal("0.00")
    assert plan.installments[-1].advance_refund_due == Decimal("25.00")
    assert plan.installments[-1].removed_from_operational_schedule


def test_surviving_boundary_row_keeps_its_fixed_daily_interest() -> None:
    plan = plan_seven_by_seven_extra_principal_tail(
        principal_reduction=Decimal("20.00"),
        future_installments=(_row(1), _row(2), _row(3, advance="20.00")),
    )

    boundary = plan.installments[-1]
    assert boundary.operational_principal_component == Decimal("9.00")
    assert boundary.signed_interest_component == Decimal("21.00")
    assert boundary.operational_amount == Decimal("30.00")
    assert boundary.advance_allocated == Decimal("20.00")
    assert boundary.advance_retained == Decimal("20.00")
    assert boundary.advance_refund_due == Decimal("0.00")


def test_boundary_row_with_excess_advance_keeps_needed_amount_and_refunds_excess() -> None:
    plan = plan_seven_by_seven_extra_principal_tail(
        principal_reduction=Decimal("20.00"),
        future_installments=(_row(1), _row(2), _row(3, advance="35.00")),
    )

    boundary = plan.installments[-1]
    assert boundary.operational_amount == Decimal("30.00")
    assert boundary.advance_allocated == Decimal("35.00")
    assert boundary.advance_retained == Decimal("30.00")
    assert boundary.advance_refund_due == Decimal("5.00")
    assert plan.advance_refund_due == Decimal("5.00")
    assert boundary.advance_retained + boundary.advance_refund_due == boundary.advance_allocated


def test_second_extra_principal_uses_prior_operational_tail_and_preserves_signed_row() -> None:
    plan = plan_seven_by_seven_extra_principal_tail(
        principal_reduction=Decimal("5.00"),
        future_installments=(
            _row(1),
            _row(2),
            _row(
                3,
                principal="9.00",
                interest="21.00",
                advance="30.00",
                signed_principal="29.00",
                signed_interest="21.00",
            ),
        ),
    )

    boundary = plan.installments[-1]
    assert plan.prior_future_principal == Decimal("67.00")
    assert plan.resulting_future_principal == Decimal("62.00")
    assert boundary.signed_contractual_amount == Decimal("50.00")
    assert boundary.signed_principal_component == Decimal("29.00")
    assert boundary.prior_operational_amount == Decimal("30.00")
    assert boundary.prior_operational_principal_component == Decimal("9.00")
    assert boundary.operational_amount == Decimal("25.00")
    assert boundary.operational_principal_component == Decimal("4.00")
    assert boundary.advance_retained == Decimal("25.00")
    assert boundary.advance_refund_due == Decimal("5.00")


def test_extra_principal_rejects_operational_interest_that_rewrites_signed_interest() -> None:
    with pytest.raises(SevenBySevenExtraPrincipalError) as captured:
        plan_seven_by_seven_extra_principal_tail(
            principal_reduction=Decimal("1.00"),
            future_installments=(
                _row(
                    1,
                    principal="20.00",
                    interest="20.00",
                    signed_principal="29.00",
                    signed_interest="21.00",
                ),
            ),
        )

    assert captured.value.code == "seven_by_seven_extra_principal_installment_invalid"


def test_extra_principal_cannot_exceed_future_principal_tail() -> None:
    with pytest.raises(SevenBySevenExtraPrincipalError) as captured:
        plan_seven_by_seven_extra_principal_tail(
            principal_reduction=Decimal("88.00"),
            future_installments=(_row(1), _row(2), _row(3)),
        )

    assert captured.value.code == "seven_by_seven_extra_principal_exceeds_future_principal"


def test_full_future_principal_reduction_removes_future_interest_and_refunds_advances() -> None:
    plan = plan_seven_by_seven_extra_principal_tail(
        principal_reduction=Decimal("87.00"),
        future_installments=(
            _row(1, advance="10.00"),
            _row(2),
            _row(3, advance="25.00"),
        ),
    )

    assert plan.resulting_future_principal == Decimal("0.00")
    assert plan.removed_future_interest == Decimal("63.00")
    assert plan.advance_refund_due == Decimal("35.00")
    assert plan.removed_installment_ids == (101, 102, 103)
    assert all(row.operational_amount == Decimal("0.00") for row in plan.installments)
    assert all(row.advance_retained == Decimal("0.00") for row in plan.installments)
    assert sum((row.advance_refund_due for row in plan.installments), Decimal("0.00")) == Decimal("35.00")
