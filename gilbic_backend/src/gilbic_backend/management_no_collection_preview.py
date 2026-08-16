from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .management_no_collection_query_repository import NoCollectionLoanState
from .management_no_collection_repository import ManagementNoCollectionConflict
from .no_collection_schedule import (
    NoCollectionScheduleError,
    OperationalInstallment,
    ScheduleShift,
    plan_no_collection_shift,
)


@dataclass(frozen=True, slots=True)
class NoCollectionPreview:
    loan_id: str
    operational_version: int
    no_collection_date: date
    payment_frequency: str
    shifts: tuple[ScheduleShift, ...]


def preview_no_collection_shift(
    *,
    state: NoCollectionLoanState,
    no_collection_date: date,
) -> NoCollectionPreview:
    """Build the exact server-side shift proposal without writing anything."""

    blocked_dates = tuple(
        item.no_collection_date for item in state.active_no_collection
    )
    installments = tuple(
        OperationalInstallment(
            installment_id=item.installment_id,
            installment_number=item.installment_number,
            contractual_due_date=item.contractual_due_date,
            effective_due_date=item.effective_due_date,
            contractual_amount=item.contractual_amount,
            allocated_amount=item.allocated_amount,
        )
        for item in state.installments
    )
    try:
        shifts = plan_no_collection_shift(
            installments=installments,
            no_collection_date=no_collection_date,
            payment_frequency=state.payment_frequency,
            blocked_dates=blocked_dates,
            semi_monthly_days=state.semi_monthly_days,
        )
    except NoCollectionScheduleError as error:
        raise ManagementNoCollectionConflict(str(error)) from error

    return NoCollectionPreview(
        loan_id=str(state.loan_id),
        operational_version=state.operational_version,
        no_collection_date=no_collection_date,
        payment_frequency=state.payment_frequency,
        shifts=shifts,
    )
