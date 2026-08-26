from __future__ import annotations

from decimal import Decimal
from typing import Any

from spina_mobile_collections.contracts import CollectionCommand, CollectionEntryType
from spina_mobile_collections.service import CollectionRejected

from .seven_by_seven_advance_activation import (
    SevenBySevenAdvanceActivationError,
    reconcile_verified_seven_by_seven_advance_before_collection,
    replay_verified_seven_by_seven_financial_state,
)
from .seven_by_seven_operational_allocator import (
    SevenBySevenAllocationError,
    SevenBySevenCashEvent,
    allocate_seven_by_seven_payments,
    money,
)
from .seven_by_seven_verified_advance_posting import (
    VerifiedAdvanceSevenBySevenCollectionPostingBridge,
)


class MaturingVerifiedAdvanceSevenBySevenCollectionPostingBridge(
    VerifiedAdvanceSevenBySevenCollectionPostingBridge
):
    """Activate verified 7x7 Advance only when its signed row becomes due."""

    def _validate_loan_and_route(
        self,
        cursor: Any,
        *,
        loan: dict[str, Any],
        collector_user_id,
        command: CollectionCommand,
    ) -> None:
        super()._validate_loan_and_route(
            cursor,
            loan=loan,
            collector_user_id=collector_user_id,
            command=command,
        )

        # This hook is reached by the shared posting bridge for Regular loans too.
        # Matured-Advance reconciliation belongs only to protected 7x7 loans; do
        # not make an ordinary Regular leg fail the 7x7 mode revalidation gate.
        if str(loan.get("calculation_mode") or "") != "seven_by_seven":
            return
        if command.entry_type not in {
            CollectionEntryType.PAYMENT,
            CollectionEntryType.ADVANCE,
        }:
            return

        # Do not mutate financial state if the loan type itself no longer passes
        # the protected 7x7 gates. The caller repeats this revalidation after the
        # route check, but doing it here keeps activation fail-closed too.
        self._revalidate_seven_by_seven_mode(loan)
        try:
            reconcile_verified_seven_by_seven_advance_before_collection(
                cursor,
                loan=loan,
                through_date=command.collection_date,
            )
        except SevenBySevenAdvanceActivationError as error:
            raise CollectionRejected(str(error), code=error.code) from error

    def _allocate_seven_by_seven_pending_event(
        self,
        cursor: Any,
        *,
        loan: dict[str, Any],
        command: CollectionCommand,
        amount: Decimal,
        previous_balance: Decimal,
    ):
        payment_start = loan["date_released"] + __import__("datetime").timedelta(days=1)
        try:
            historical = replay_verified_seven_by_seven_financial_state(
                cursor,
                loan_id=loan["loan_id"],
                original_principal=money(loan["principal"]),
                daily_interest_per_1000=money(loan["daily_interest_per_1000"]),
                payment_start=payment_start,
                through_date=command.collection_date,
            )
        except SevenBySevenAdvanceActivationError as error:
            raise CollectionRejected(str(error), code=error.code) from error

        if historical.result.closing_remaining_principal != previous_balance:
            raise CollectionRejected(
                "The 7x7 operational balance does not match the matured Advance replay. "
                "Management reconciliation is required.",
                code="seven_by_seven_balance_not_reconciled",
            )
        if historical.result.complete:
            raise CollectionRejected(
                "This 7x7 loan is already fully paid. Refresh the route.",
                code="loan_already_paid",
            )

        pending_event = SevenBySevenCashEvent(
            event_id=f"pending:{command.idempotency_key}",
            collection_date=command.collection_date,
            amount=amount,
        )
        try:
            result = allocate_seven_by_seven_payments(
                original_principal=money(loan["principal"]),
                daily_interest_per_1000=money(loan["daily_interest_per_1000"]),
                payment_start=payment_start,
                events=(*historical.historical_events, pending_event),
            )
        except SevenBySevenAllocationError as error:
            raise CollectionRejected(
                "This 7x7 entry cannot be allocated after matured Advance without "
                "changing the protected interest-first order.",
                code="seven_by_seven_allocation_conflict",
            ) from error
        return result, result.allocations[-1]
