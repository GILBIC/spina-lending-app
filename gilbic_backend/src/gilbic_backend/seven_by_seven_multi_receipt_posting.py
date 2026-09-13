from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb
from spina_mobile_collections.contracts import (
    ActorContext,
    CollectionCommand,
    CollectionEntryType,
    PaymentAllocationIntent,
    PostedCollection,
)
from spina_mobile_collections.service import CollectionRejected

from .seven_by_seven_no_collection_voluntary_posting import (
    NoCollectionVoluntarySevenBySevenCollectionPostingBridge,
)
from .seven_by_seven_penalty_coordinator import (
    SevenBySevenPenaltyCoordinatorError,
    freeze_verified_seven_by_seven_penalty_assessment,
    project_verified_seven_by_seven_penalty_state,
)


ZERO = Decimal("0.00")


class MultiReceiptSevenBySevenCollectionPostingBridge(
    NoCollectionVoluntarySevenBySevenCollectionPostingBridge
):
    """Permit legitimate distinct 7x7 receipts on one client/date.

    Idempotency and device-sequence controls still reject a technical retry of
    the same transaction. What is removed here is only the older date-level
    assumption that a second real cash receipt must be a duplicate.

    Normal 7x7 PAYMENT receipts do not claim an exclusive
    ``collection_covered_dates`` row. Verified ADVANCE also uses signed
    installment-allocation evidence as its authority, so a later partial Advance
    may continue the same future row without turning that row into a duplicate
    cash receipt. Matured verified Advance is financially activated only when
    its effective signed row date is reached.

    No Collection voluntary receipts reuse the same protected post-maturity
    penalty coordinator as normal 7x7 collection. The NC planner still owns only
    contractual cash: it never computes or allocates penalty locally. When the
    receipt is post-maturity, the transaction is inserted first and then becomes
    the financial-boundary source for the coordinator's immutable assessment.
    """

    def _insert_collection_transaction(
        self,
        cursor: Any,
        *,
        transaction_id: UUID,
        command: CollectionCommand,
        loan_id: UUID,
        client_id: UUID,
        collector_user_id: UUID,
        registered_device_id: UUID,
        route_entry_id: UUID,
        amount: Decimal,
        accepted_at,
        previous_balance: Decimal,
        official_balance: Decimal,
        pass_count_after: int,
        advance_until_after: date | None,
        receipt_number: str,
        details: dict[str, object],
    ) -> None:
        if (
            command.payment_allocation_intent
            is not PaymentAllocationIntent.NO_COLLECTION_VOLUNTARY
        ):
            return super()._insert_collection_transaction(
                cursor,
                transaction_id=transaction_id,
                command=command,
                loan_id=loan_id,
                client_id=client_id,
                collector_user_id=collector_user_id,
                registered_device_id=registered_device_id,
                route_entry_id=route_entry_id,
                amount=amount,
                accepted_at=accepted_at,
                previous_balance=previous_balance,
                official_balance=official_balance,
                pass_count_after=pass_count_after,
                advance_until_after=advance_until_after,
                receipt_number=receipt_number,
                details=details,
            )

        try:
            penalty_state = project_verified_seven_by_seven_penalty_state(
                cursor,
                loan_id=loan_id,
                as_of_date=command.collection_date,
            )
        except SevenBySevenPenaltyCoordinatorError as error:
            raise CollectionRejected(
                str(error),
                code="seven_by_seven_penalty_management_review_required",
            ) from error

        penalty_post_maturity = (
            penalty_state.contractual_maturity is not None
            and command.collection_date > penalty_state.contractual_maturity
        )
        if (
            penalty_post_maturity
            and penalty_state.status == "management_review_required"
        ):
            raise CollectionRejected(
                penalty_state.management_review_required_reason
                or "Management review is required before collecting this post-maturity 7x7 payment.",
                code="seven_by_seven_penalty_management_review_required",
            )

        penalty_due = self._money(
            penalty_state.assessed_penalty_balance + penalty_state.projected_penalty
        )
        if penalty_post_maturity:
            details = {
                **details,
                "seven_by_seven_penalty_assessed": str(
                    self._money(penalty_state.projected_penalty)
                ),
                "seven_by_seven_penalty_paid": "0.00",
                "seven_by_seven_penalty_outstanding": str(penalty_due),
                "seven_by_seven_penalty_status": penalty_state.status,
            }

        super()._insert_collection_transaction(
            cursor,
            transaction_id=transaction_id,
            command=command,
            loan_id=loan_id,
            client_id=client_id,
            collector_user_id=collector_user_id,
            registered_device_id=registered_device_id,
            route_entry_id=route_entry_id,
            amount=amount,
            accepted_at=accepted_at,
            previous_balance=previous_balance,
            official_balance=official_balance,
            pass_count_after=pass_count_after,
            advance_until_after=advance_until_after,
            receipt_number=receipt_number,
            details=details,
        )

        if not penalty_post_maturity:
            return

        try:
            frozen_penalty = freeze_verified_seven_by_seven_penalty_assessment(
                cursor,
                loan_id=loan_id,
                through_date=command.collection_date,
                source_transaction_id=transaction_id,
            )
            final_penalty = project_verified_seven_by_seven_penalty_state(
                cursor,
                loan_id=loan_id,
                as_of_date=command.collection_date,
            )
        except SevenBySevenPenaltyCoordinatorError as error:
            raise CollectionRejected(
                str(error),
                code="seven_by_seven_penalty_management_review_required",
            ) from error

        if frozen_penalty.status == "management_review_required":
            raise CollectionRejected(
                frozen_penalty.management_review_required_reason
                or "Management review is required before assessing this 7x7 penalty.",
                code="seven_by_seven_penalty_management_review_required",
            )
        if final_penalty.status == "management_review_required":
            raise CollectionRejected(
                final_penalty.management_review_required_reason
                or "Management review is required before completing this 7x7 payment.",
                code="seven_by_seven_penalty_management_review_required",
            )

        final_outstanding = self._money(final_penalty.assessed_penalty_balance)
        if final_outstanding != penalty_due:
            raise CollectionRejected(
                "The post-maturity 7x7 penalty changed while the No Collection voluntary payment was being saved. Refresh and review the exact obligation.",
                code="seven_by_seven_penalty_management_review_required",
            )

        if final_outstanding > ZERO:
            cursor.execute(
                """
                update lending.loans
                set status = 'active', updated_at = %s
                where id = %s
                  and status = 'paid'
                """,
                (accepted_at, loan_id),
            )

    def _verify_seven_by_seven_date_available(
        self,
        cursor: Any,
        *,
        loan_id: UUID,
        collection_date: date,
        entry_type: CollectionEntryType,
    ) -> None:
        # A date is not a PAYMENT/ADVANCE transaction identity, so legitimate
        # same-day cash receipts remain allowed. PASS is different: it is one
        # day-level Unable-to-Pay decision and must still use the base guard so
        # it cannot be added after another receipt or duplicated on the date.
        return super()._verify_seven_by_seven_date_available(
            cursor,
            loan_id=loan_id,
            collection_date=collection_date,
            entry_type=entry_type,
        )

    @staticmethod
    def _seven_by_seven_covered_dates(command: CollectionCommand) -> tuple[date, ...]:
        if command.entry_type is CollectionEntryType.PASS:
            return ()

        selected = tuple(sorted(set(command.covered_dates)))
        if command.entry_type is CollectionEntryType.PAYMENT:
            # Older clients send today's date for normal Payment. Accept that
            # wire shape for compatibility, but do not turn it into an exclusive
            # covered-date claim. Today's obligation is derived from aggregate
            # receipt/allocation state instead.
            if selected and selected != (command.collection_date,):
                raise CollectionRejected(
                    "A normal 7x7 payment may reference only its collection date. "
                    "Use Details for Advance or Extra Principal.",
                    code="seven_by_seven_payment_coverage_invalid",
                )
            return ()

        return selected
