from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from psycopg.rows import dict_row

from .collection_correction_repository import (
    CollectionCorrectionInvalid,
    CollectionCorrectionRecord,
    PostgresCollectionCorrectionRepository,
)
from .database import open_connection


class ContractSafeCollectionCorrectionRepository(
    PostgresCollectionCorrectionRepository
):
    """Keep contract-aware collections immutable through the legacy edit route.

    Once a collection has been validated against a signed contractual schedule,
    changing its amount/type/dates without rebuilding installment allocations
    would make the schedule evidence stale. For an unlocked mistake the safe
    workflow is therefore void the receipt and record a corrected collection.
    """

    def correct_own_unremitted(
        self,
        *,
        actor_user_id: UUID,
        transaction_id: UUID,
        entry_type: str,
        amount: Decimal | None,
        covered_dates: tuple[date, ...],
        note: str,
        reason: str,
        expected_route_revision: str,
    ) -> CollectionCorrectionRecord:
        if self._is_contract_controlled(transaction_id=transaction_id):
            raise CollectionCorrectionInvalid(
                "This collection is tied to a verified contractual schedule. "
                "Void the unremitted receipt and record the corrected collection "
                "again instead of editing it."
            )
        return super().correct_own_unremitted(
            actor_user_id=actor_user_id,
            transaction_id=transaction_id,
            entry_type=entry_type,
            amount=amount,
            covered_dates=covered_dates,
            note=note,
            reason=reason,
            expected_route_revision=expected_route_revision,
        )

    @staticmethod
    def _is_contract_controlled(*, transaction_id: UUID) -> bool:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    select
                        exists (
                            select 1
                            from lending.loan_installment_payment_allocations allocation
                            where allocation.transaction_id = transaction.id
                        ) as has_contract_allocation,
                        lower(coalesce(
                            transaction.details
                                -> 'contract_schedule_allocation'
                                ->> 'enabled',
                            ''
                        )) in ('true', '1', 'yes', 'on') as contract_validated
                    from lending.collection_transactions transaction
                    where transaction.id = %s
                    """,
                    (transaction_id,),
                )
                row = cursor.fetchone()
        return bool(
            row
            and (
                row["has_contract_allocation"]
                or row["contract_validated"]
            )
        )
