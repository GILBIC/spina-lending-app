from __future__ import annotations

from datetime import date
from decimal import Decimal

from gilbic_backend.no_collection_schedule import (
    OperationalInstallment,
    plan_no_collection_shift,
)
from gilbic_backend.rolling_schedule import (
    RollingScheduleInstallment,
    finalize_rolling_schedule_day,
    project_rolling_schedule,
)
from gilbic_backend.seven_by_seven_no_collection_voluntary import (
    NoCollectionAffectedInstallment,
    plan_seven_by_seven_no_collection_voluntary_payment,
)


NC_DATE = date(2026, 8, 29)
SHIFTED_DATE = date(2026, 8, 30)


def test_partial_payment_before_management_no_collection_stays_with_shifted_row() -> None:
    target = OperationalInstallment(
        installment_id=20,
        installment_number=20,
        contractual_due_date=NC_DATE,
        effective_due_date=NC_DATE,
        contractual_amount=Decimal("50.00"),
        allocated_amount=Decimal("20.00"),
    )
    later = OperationalInstallment(
        installment_id=21,
        installment_number=21,
        contractual_due_date=SHIFTED_DATE,
        effective_due_date=SHIFTED_DATE,
        contractual_amount=Decimal("50.00"),
    )

    shifts = plan_no_collection_shift(
        installments=(target, later),
        no_collection_date=NC_DATE,
        payment_frequency="daily",
    )

    assert shifts[0].installment_id == target.installment_id
    assert shifts[0].prior_effective_due_date == NC_DATE
    assert shifts[0].new_effective_due_date == SHIFTED_DATE
    assert target.allocated_amount == Decimal("20.00")


def test_partial_voluntary_no_collection_payment_keeps_shift_and_holiday() -> None:
    plan = plan_seven_by_seven_no_collection_voluntary_payment(
        transaction_amount=Decimal("20.00"),
        collection_date=NC_DATE,
        no_collection_date=NC_DATE,
        past_due_obligations=(),
        affected_installment=NoCollectionAffectedInstallment(
            installment_id=20,
            installment_number=20,
            contractual_amount=Decimal("50.00"),
        ),
    )

    assert plan.status == "partial_shifted_prepayment"
    assert plan.shifted_prepayment_amount == Decimal("20.00")
    assert plan.keep_no_collection_shift is True
    assert plan.keep_interest_holiday is True


def test_partial_no_collection_row_does_not_add_second_extension_on_original_date() -> None:
    rows = (
        RollingScheduleInstallment(
            installment_id=20,
            installment_number=20,
            contractual_due_date=NC_DATE,
            effective_due_date=SHIFTED_DATE,
            remaining_amount=Decimal("30.00"),
        ),
        RollingScheduleInstallment(
            installment_id=21,
            installment_number=21,
            contractual_due_date=SHIFTED_DATE,
            effective_due_date=date(2026, 8, 31),
            remaining_amount=Decimal("50.00"),
        ),
    )

    original_close = finalize_rolling_schedule_day(
        installments=rows,
        business_date=NC_DATE,
    )
    original_projection = project_rolling_schedule(
        installments=rows,
        as_of_date=NC_DATE,
        payment_frequency="daily",
        blocked_dates=(NC_DATE,),
        finalized_through_date=NC_DATE,
    )

    assert original_close.close_status == "no_scheduled_obligation"
    assert original_close.extension_slots_added == 0
    assert original_projection.extension_slots == 0
    assert original_projection.updated_maturity == date(2026, 8, 31)

    shifted_close = finalize_rolling_schedule_day(
        installments=rows,
        business_date=SHIFTED_DATE,
    )
    shifted_projection = project_rolling_schedule(
        installments=rows,
        as_of_date=SHIFTED_DATE,
        payment_frequency="daily",
        blocked_dates=(NC_DATE,),
        finalized_through_date=SHIFTED_DATE,
    )

    assert shifted_close.close_status == "shortfall"
    assert shifted_close.shortfall_amount == Decimal("30.00")
    assert shifted_close.extension_slots_added == 1
    assert shifted_projection.extension_slots == 1
    assert shifted_projection.updated_maturity == date(2026, 9, 1)
