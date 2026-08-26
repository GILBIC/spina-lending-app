from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from spina_mobile_collections.contracts import CollectionCommand, CollectionEntryType
from spina_mobile_collections.service import CollectionRejected

from .seven_by_seven_collection_posting import (
    SevenBySevenAwarePerLoanContractCollectionPostingBridge,
)


class MultiReceiptSevenBySevenCollectionPostingBridge(
    SevenBySevenAwarePerLoanContractCollectionPostingBridge
):
    """Permit legitimate distinct 7x7 receipts on one client/date.

    Idempotency and device-sequence controls still reject a technical retry of
    the same transaction. What is removed here is only the older date-level
    assumption that a second real cash receipt must be a duplicate.

    Normal 7x7 PAYMENT receipts no longer claim the exclusive
    ``collection_covered_dates`` row. That table remains reserved for explicit
    ADV / covered-date intent, where exclusivity is still required. The 7x7
    operational allocator replays all positive receipts and aggregates same-day
    cash without accruing daily interest twice.
    """

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
                    "Use ADV / exact covered dates when the client intends to pay future dates.",
                    code="seven_by_seven_payment_coverage_invalid",
                )
            return ()

        return selected
