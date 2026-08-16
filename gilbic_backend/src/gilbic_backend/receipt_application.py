from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal


MONEY = Decimal("0.01")
ReceiptAllocationState = Literal[
    "fully_allocated",
    "partially_allocated",
    "unallocated",
]
ReceiptAllocationIntent = Literal[
    "scheduled",
    "voluntary_extra",
    "advance",
]


class ReceiptApplicationError(ValueError):
    """Raised when a real receipt cannot be classified safely."""


@dataclass(frozen=True, slots=True)
class ReceiptApplicationPlan:
    cash_received_amount: Decimal
    applied_amount: Decimal
    unallocated_amount: Decimal
    allocation_state: ReceiptAllocationState
    allocation_intent: ReceiptAllocationIntent

    @property
    def needs_review(self) -> bool:
        return self.unallocated_amount > Decimal("0.00")


def plan_receipt_application(
    *,
    cash_received_amount: Decimal | int | str,
    maximum_immediately_applicable: Decimal | int | str,
    allocation_intent: ReceiptAllocationIntent,
) -> ReceiptApplicationPlan:
    """Split one real receipt into applied and unresolved custody cash.

    ``maximum_immediately_applicable`` is supplied by the authoritative loan
    allocator for the chosen intent:

    - scheduled: current eligible scheduled obligation only;
    - voluntary_extra: eligible loan balance allowed to be reduced now;
    - advance: explicitly selected future covered-date obligation only.

    Cash above that maximum is not rejected and is never guessed into another
    purpose. It remains an audited unallocated amount for the assigned Collector
    or Management to resolve while the receipt itself continues through custody
    and remittance.
    """

    cash = _money(cash_received_amount)
    maximum = _money(maximum_immediately_applicable)
    if cash <= 0:
        raise ReceiptApplicationError("Cash received must be greater than zero.")
    if maximum < 0:
        raise ReceiptApplicationError(
            "Maximum immediately applicable amount cannot be negative."
        )
    if allocation_intent not in {"scheduled", "voluntary_extra", "advance"}:
        raise ReceiptApplicationError("Unsupported receipt allocation intent.")

    applied = min(cash, maximum)
    unallocated = _money(cash - applied)
    if applied == cash:
        state: ReceiptAllocationState = "fully_allocated"
    elif applied > 0:
        state = "partially_allocated"
    else:
        state = "unallocated"

    return ReceiptApplicationPlan(
        cash_received_amount=cash,
        applied_amount=_money(applied),
        unallocated_amount=unallocated,
        allocation_state=state,
        allocation_intent=allocation_intent,
    )


def _money(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)
