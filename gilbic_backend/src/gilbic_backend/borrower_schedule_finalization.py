from __future__ import annotations

from datetime import date
from uuid import UUID

from .borrower_schedule_adjustment_repository import BorrowerScheduleAdjustmentRecord


class PostgresBorrowerScheduleFinalizer:
    def finalize_elapsed_for_loans(
        self,
        *,
        actor_user_id: UUID,
        loan_ids: tuple[UUID, ...],
        business_date: date,
    ) -> tuple[BorrowerScheduleAdjustmentRecord, ...]:
        return ()
