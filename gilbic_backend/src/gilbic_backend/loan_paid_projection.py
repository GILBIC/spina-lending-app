"""Shared applied-receipt and registered-contract projection for loan readers."""

from decimal import Decimal

# Trusted SQL for queries whose lending.loans alias is `loan`. Financial read
# owners use one source definition; no principal/balance arithmetic implies cash.
PAID_PROJECTION_COLUMNS = """
    (
        select sum(installment.contractual_amount)
        from lending.loan_contract_schedules schedule
        join lending.loan_contract_schedule_registrations registration
          on registration.schedule_id = schedule.id
        join lending.loan_contract_installments installment
          on installment.schedule_id = schedule.id
        where schedule.loan_id = loan.id
          and schedule.status = 'active'
    ) as contractual_total,
    coalesce((
        select sum(tx.applied_amount)
        from lending.collection_transactions tx
        where tx.loan_id = loan.id
          and tx.is_voided = false
          and tx.entry_type in ('payment', 'advance')
    ), 0)::numeric(18,2) as paid_amount
"""


def paid_percentage(
    paid_amount: Decimal, contractual_total: Decimal | None
) -> Decimal | None:
    """Unavailable contracts stay unknown; this is a display ratio, not eligibility."""
    if contractual_total is None or contractual_total <= 0:
        return None
    return min(
        Decimal("100.0"),
        (paid_amount / contractual_total * Decimal(100)).quantize(Decimal("0.1")),
    )
