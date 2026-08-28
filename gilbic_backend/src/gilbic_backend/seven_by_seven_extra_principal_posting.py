from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb
from spina_mobile_collections.contracts import PaymentAllocationIntent

from .seven_by_seven_extra_principal import (
    FutureInstallmentPrincipalState,
    SevenBySevenExtraPrincipalError,
    SevenBySevenExtraPrincipalPlan,
    plan_seven_by_seven_extra_principal_tail,
)
from .seven_by_seven_extra_principal_replay import (
    ActiveExtraPrincipalEvent,
    ExtraPrincipalReplayResult,
    SevenBySevenExtraPrincipalReplayError,
    replay_extra_principal_history,
    require_extra_principal_interest_clear,
)
from .seven_by_seven_operational_allocator import ZERO, money


class ExtraPrincipalPostingRejected(ValueError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class SevenBySevenExtraPrincipalPostingResult:
    adjustment_id: UUID
    principal_reduction: Decimal
    resulting_future_principal: Decimal
    removed_future_interest: Decimal
    retained_advance: Decimal
    refund_due: Decimal
    resulting_operational_version: int
    operational_state_digest: str

    def response_metadata(self) -> dict[str, object]:
        return {
            "allocation_type": "seven_by_seven_extra_principal",
            "adjustment_id": str(self.adjustment_id),
            "principal_reduction": _money_text(self.principal_reduction),
            "interest_contribution": "0.00",
            "resulting_future_principal": _money_text(self.resulting_future_principal),
            "removed_future_interest": _money_text(self.removed_future_interest),
            "retained_advance": _money_text(self.retained_advance),
            "refund_due": _money_text(self.refund_due),
            "resulting_operational_version": self.resulting_operational_version,
            "operational_state_digest": self.operational_state_digest,
            "automatic_source_posting": False,
        }


@dataclass(frozen=True, slots=True)
class _LockedExtraPrincipalState:
    schedule_id: UUID
    expected_operational_version: int
    signed_installments: tuple[FutureInstallmentPrincipalState, ...]
    active_events: tuple[ActiveExtraPrincipalEvent, ...]
    replayed: ExtraPrincipalReplayResult
    future_installments: tuple[FutureInstallmentPrincipalState, ...]


def require_modern_extra_principal_intent(
    payment_allocation_intent: PaymentAllocationIntent,
) -> None:
    if (
        payment_allocation_intent
        is not PaymentAllocationIntent.EXTRA_AS_PRINCIPAL_REDUCTION
    ):
        raise ExtraPrincipalPostingRejected(
            "Choose Principal Reduction explicitly before saving 7x7 Extra Principal.",
            code="seven_by_seven_extra_principal_intent_required",
        )


def post_seven_by_seven_extra_principal(
    cursor: Any,
    *,
    transaction_id: UUID,
    loan_id: UUID,
    actor_user_id: UUID,
    collection_date: date,
    receipt_amount: Decimal,
    payment_allocation_intent: PaymentAllocationIntent,
    expected_route_revision: str,
    past_due_interest: Decimal,
    today_interest: Decimal,
) -> SevenBySevenExtraPrincipalPostingResult:
    """Persist one protected principal-only 7x7 effect beside its receipt.

    The official receipt must already exist in the caller's open PostgreSQL
    transaction. Any rejection raised here therefore rolls that receipt and all
    operational effects back together at the executor boundary.
    """

    require_modern_extra_principal_intent(payment_allocation_intent)
    amount = money(receipt_amount)
    if amount <= ZERO:
        raise ExtraPrincipalPostingRejected(
            "7x7 Extra Principal must be greater than zero.",
            code="seven_by_seven_extra_principal_amount_invalid",
        )
    try:
        require_extra_principal_interest_clear(
            past_due_interest=past_due_interest,
            today_interest=today_interest,
        )
    except SevenBySevenExtraPrincipalReplayError as error:
        raise _posting_rejection(error) from error

    _validate_source_receipt(
        cursor,
        transaction_id=transaction_id,
        loan_id=loan_id,
        actor_user_id=actor_user_id,
        collection_date=collection_date,
        receipt_amount=amount,
        expected_route_revision=expected_route_revision,
    )
    locked = _load_locked_extra_principal_state(
        cursor,
        loan_id=loan_id,
        actor_user_id=actor_user_id,
        collection_date=collection_date,
    )
    try:
        plan = plan_seven_by_seven_extra_principal_tail(
            principal_reduction=amount,
            future_installments=locked.future_installments,
        )
    except SevenBySevenExtraPrincipalError as error:
        raise _posting_rejection(error) from error

    adjustment_id = uuid4()
    resulting_version = locked.expected_operational_version + 1
    try:
        replayed_after = replay_extra_principal_history(
            signed_installments=locked.signed_installments,
            active_events=(
                *locked.active_events,
                ActiveExtraPrincipalEvent(
                    adjustment_id=adjustment_id,
                    transaction_id=transaction_id,
                    principal_reduction=amount,
                    resulting_operational_version=resulting_version,
                    collection_date=collection_date,
                ),
            ),
        )
    except SevenBySevenExtraPrincipalReplayError as error:
        raise _posting_rejection(error) from error

    _verify_plan_matches_replay(
        plan=plan,
        replayed_after=replayed_after,
        adjustment_id=adjustment_id,
    )
    _store_extra_principal_plan(
        cursor,
        transaction_id=transaction_id,
        adjustment_id=adjustment_id,
        loan_id=loan_id,
        actor_user_id=actor_user_id,
        locked=locked,
        plan=plan,
        resulting_version=resulting_version,
        operational_state_digest=replayed_after.operational_state_digest,
    )

    return SevenBySevenExtraPrincipalPostingResult(
        adjustment_id=adjustment_id,
        principal_reduction=plan.principal_reduction,
        resulting_future_principal=plan.resulting_future_principal,
        removed_future_interest=plan.removed_future_interest,
        retained_advance=money(
            sum((item.advance_retained for item in plan.installments), ZERO)
        ),
        refund_due=plan.advance_refund_due,
        resulting_operational_version=resulting_version,
        operational_state_digest=replayed_after.operational_state_digest,
    )


def _validate_source_receipt(
    cursor: Any,
    *,
    transaction_id: UUID,
    loan_id: UUID,
    actor_user_id: UUID,
    collection_date: date,
    receipt_amount: Decimal,
    expected_route_revision: str,
) -> None:
    cursor.execute(
        """
        select
            transaction.loan_id,
            transaction.collector_user_id,
            transaction.collection_date,
            transaction.entry_type,
            transaction.amount,
            transaction.route_revision,
            transaction.is_voided,
            coalesce(
                transaction.details ->> 'payment_allocation_intent',
                ''
            ) as payment_allocation_intent
        from lending.collection_transactions transaction
        where transaction.id = %s
        for update
        """,
        (transaction_id,),
    )
    receipt = cursor.fetchone()
    if (
        receipt is None
        or receipt["loan_id"] != loan_id
        or receipt["collector_user_id"] != actor_user_id
        or receipt["collection_date"] != collection_date
        or str(receipt["entry_type"]) != "payment"
        or money(receipt["amount"]) != receipt_amount
        or str(receipt["route_revision"] or "") != expected_route_revision
        or bool(receipt["is_voided"])
        or str(receipt["payment_allocation_intent"])
        != PaymentAllocationIntent.EXTRA_AS_PRINCIPAL_REDUCTION.value
    ):
        raise ExtraPrincipalPostingRejected(
            "The 7x7 Extra Principal source receipt does not match its protected request.",
            code="seven_by_seven_extra_principal_receipt_mismatch",
        )


def _load_locked_extra_principal_state(
    cursor: Any,
    *,
    loan_id: UUID,
    actor_user_id: UUID,
    collection_date: date,
) -> _LockedExtraPrincipalState:
    cursor.execute(
        """
        select schedule.id, schedule.payment_frequency
        from lending.loan_contract_schedules schedule
        join lending.loan_contract_schedule_registrations registration
          on registration.schedule_id = schedule.id
        where schedule.loan_id = %s
          and schedule.status = 'active'
        order by registration.verified_at desc, schedule.id
        limit 1
        for update of schedule
        """,
        (loan_id,),
    )
    schedule = cursor.fetchone()
    if schedule is None:
        raise ExtraPrincipalPostingRejected(
            "This 7x7 loan does not yet have an active verified signed schedule.",
            code="seven_by_seven_verified_schedule_required",
        )
    if str(schedule["payment_frequency"]) != "daily":
        raise ExtraPrincipalPostingRejected(
            "The active verified 7x7 schedule is not daily. Management review is required.",
            code="seven_by_seven_extra_principal_schedule_conflict",
        )
    schedule_id = schedule["id"]

    cursor.execute(
        """
        insert into lending.loan_schedule_operational_state (
            schedule_id, operational_version, updated_by_user_id
        ) values (%s, 0, %s)
        on conflict (schedule_id) do nothing
        """,
        (schedule_id, actor_user_id),
    )
    cursor.execute(
        """
        select operational_version
        from lending.loan_schedule_operational_state
        where schedule_id = %s
        for update
        """,
        (schedule_id,),
    )
    operational_state = cursor.fetchone()
    if operational_state is None:
        raise ExtraPrincipalPostingRejected(
            "The 7x7 operational version could not be locked.",
            code="seven_by_seven_extra_principal_state_conflict",
        )
    operational_version = int(operational_state["operational_version"])

    cursor.execute(
        """
        select installment.id
        from lending.loan_contract_installments installment
        where installment.schedule_id = %s
        order by installment.id
        for update
        """,
        (schedule_id,),
    )
    installment_ids = tuple(int(row["id"]) for row in cursor.fetchall())
    if not installment_ids:
        raise ExtraPrincipalPostingRejected(
            "The active verified 7x7 schedule has no signed installment rows.",
            code="seven_by_seven_extra_principal_schedule_conflict",
        )

    cursor.execute(
        """
        select operational.installment_id
        from lending.loan_installment_operational_amounts operational
        join lending.loan_contract_installments installment
          on installment.id = operational.installment_id
        where installment.schedule_id = %s
        order by operational.installment_id
        for update of operational
        """,
        (schedule_id,),
    )
    cursor.fetchall()

    cursor.execute(
        """
        select
            installment.id,
            installment.installment_number,
            installment.effective_due_date,
            installment.contractual_amount as signed_amount,
            installment.principal_component as signed_principal,
            installment.interest_component as signed_interest,
            installment.operational_amount,
            installment.operational_principal_component,
            installment.operational_interest_component,
            installment.removed_from_operational_schedule,
            installment.last_extra_principal_adjustment_id,
            coalesce(active_advance.active_advance_allocated, 0)::numeric(18,2)
                as active_advance
        from lending.loan_contract_installments_operational installment
        left join lending.loan_installment_active_advance active_advance
          on active_advance.installment_id = installment.id
        where installment.schedule_id = %s
        order by
            installment.effective_due_date,
            installment.installment_number,
            installment.id
        """,
        (schedule_id,),
    )
    rows = cursor.fetchall()
    if {int(row["id"]) for row in rows} != set(installment_ids):
        raise ExtraPrincipalPostingRejected(
            "The locked 7x7 signed schedule changed during Extra Principal replay.",
            code="seven_by_seven_extra_principal_state_conflict",
        )

    signed_installments = tuple(
        FutureInstallmentPrincipalState(
            installment_id=int(row["id"]),
            installment_number=int(row["installment_number"]),
            effective_due_date=row["effective_due_date"],
            contractual_amount=money(row["signed_amount"]),
            principal_component=money(row["signed_principal"]),
            interest_component=money(row["signed_interest"]),
            signed_contractual_amount=money(row["signed_amount"]),
            signed_principal_component=money(row["signed_principal"]),
            signed_interest_component=money(row["signed_interest"]),
        )
        for row in rows
    )

    cursor.execute(
        """
        select
            adjustment.id,
            adjustment.transaction_id,
            adjustment.principal_reduction,
            adjustment.resulting_operational_version,
            transaction.collection_date
        from lending.seven_by_seven_extra_principal_adjustments adjustment
        join lending.collection_transactions transaction
          on transaction.id = adjustment.transaction_id
        left join lending.seven_by_seven_extra_principal_reversals reversal
          on reversal.adjustment_id = adjustment.id
        where adjustment.schedule_id = %s
          and reversal.id is null
        order by adjustment.resulting_operational_version, adjustment.id
        for update of adjustment
        """,
        (schedule_id,),
    )
    active_events = tuple(
        ActiveExtraPrincipalEvent(
            adjustment_id=row["id"],
            transaction_id=row["transaction_id"],
            principal_reduction=money(row["principal_reduction"]),
            resulting_operational_version=int(row["resulting_operational_version"]),
            collection_date=row["collection_date"],
        )
        for row in cursor.fetchall()
    )
    try:
        replayed = replay_extra_principal_history(
            signed_installments=signed_installments,
            active_events=active_events,
        )
    except SevenBySevenExtraPrincipalReplayError as error:
        raise _posting_rejection(error) from error

    actual_by_id = {int(row["id"]): row for row in rows}
    for replayed_row in replayed.operational_rows:
        actual = actual_by_id[replayed_row.installment_id]
        if (
            money(actual["operational_amount"]) != replayed_row.operational_amount
            or money(actual["operational_principal_component"])
            != replayed_row.operational_principal
            or money(actual["operational_interest_component"])
            != replayed_row.operational_interest
            or bool(actual["removed_from_operational_schedule"]) != replayed_row.removed
            or actual["last_extra_principal_adjustment_id"]
            != replayed_row.last_active_adjustment_id
        ):
            raise ExtraPrincipalPostingRejected(
                "The persisted 7x7 operational tail does not match immutable Extra Principal history.",
                code="seven_by_seven_extra_principal_replay_conflict",
            )

    future_installments = tuple(
        FutureInstallmentPrincipalState(
            installment_id=replayed_row.installment_id,
            installment_number=replayed_row.installment_number,
            effective_due_date=replayed_row.effective_due_date,
            contractual_amount=replayed_row.operational_amount,
            principal_component=replayed_row.operational_principal,
            interest_component=replayed_row.operational_interest,
            advance_allocated=money(
                actual_by_id[replayed_row.installment_id]["active_advance"]
            ),
            signed_contractual_amount=replayed_row.signed_amount,
            signed_principal_component=replayed_row.signed_principal,
            signed_interest_component=replayed_row.signed_interest,
        )
        for replayed_row in replayed.operational_rows
        if not replayed_row.removed
        and replayed_row.effective_due_date > collection_date
    )
    return _LockedExtraPrincipalState(
        schedule_id=schedule_id,
        expected_operational_version=operational_version,
        signed_installments=signed_installments,
        active_events=active_events,
        replayed=replayed,
        future_installments=future_installments,
    )


def _verify_plan_matches_replay(
    *,
    plan: SevenBySevenExtraPrincipalPlan,
    replayed_after: ExtraPrincipalReplayResult,
    adjustment_id: UUID,
) -> None:
    replayed_by_id = {
        row.installment_id: row for row in replayed_after.operational_rows
    }
    for item in plan.installments:
        replayed = replayed_by_id.get(item.installment_id)
        if (
            replayed is None
            or replayed.operational_amount != item.operational_amount
            or replayed.operational_principal != item.operational_principal_component
            or replayed.removed != item.removed_from_operational_schedule
            or replayed.last_active_adjustment_id != adjustment_id
        ):
            raise ExtraPrincipalPostingRejected(
                "The projected 7x7 Extra Principal tail does not match deterministic replay.",
                code="seven_by_seven_extra_principal_replay_conflict",
            )


def _store_extra_principal_plan(
    cursor: Any,
    *,
    transaction_id: UUID,
    adjustment_id: UUID,
    loan_id: UUID,
    actor_user_id: UUID,
    locked: _LockedExtraPrincipalState,
    plan: SevenBySevenExtraPrincipalPlan,
    resulting_version: int,
    operational_state_digest: str,
) -> None:
    cursor.execute(
        """
        insert into lending.seven_by_seven_extra_principal_adjustments (
            id,
            loan_id,
            schedule_id,
            transaction_id,
            principal_reduction,
            prior_future_principal,
            resulting_future_principal,
            removed_future_interest,
            advance_refund_due,
            expected_operational_version,
            resulting_operational_version,
            actor_user_id
        ) values (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        """,
        (
            adjustment_id,
            loan_id,
            locked.schedule_id,
            transaction_id,
            plan.principal_reduction,
            plan.prior_future_principal,
            plan.resulting_future_principal,
            plan.removed_future_interest,
            plan.advance_refund_due,
            locked.expected_operational_version,
            resulting_version,
            actor_user_id,
        ),
    )

    for item in plan.installments:
        prior_interest = money(
            item.prior_operational_amount - item.prior_operational_principal_component
        )
        new_interest = (
            ZERO
            if item.removed_from_operational_schedule
            else item.signed_interest_component
        )
        cursor.execute(
            """
            insert into lending.seven_by_seven_extra_principal_adjustment_items (
                adjustment_id,
                installment_id,
                installment_number,
                effective_due_date,
                signed_contractual_amount,
                signed_principal_component,
                signed_interest_component,
                prior_operational_amount,
                prior_operational_principal_component,
                prior_operational_interest_component,
                new_operational_amount,
                new_operational_principal_component,
                new_operational_interest_component,
                advance_allocated_before,
                advance_retained_after,
                advance_refund_due,
                removed_from_operational_schedule
            ) values (
                %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s
            )
            """,
            (
                adjustment_id,
                item.installment_id,
                item.installment_number,
                item.effective_due_date,
                item.signed_contractual_amount,
                item.signed_principal_component,
                item.signed_interest_component,
                item.prior_operational_amount,
                item.prior_operational_principal_component,
                prior_interest,
                item.operational_amount,
                item.operational_principal_component,
                new_interest,
                item.advance_allocated,
                item.advance_retained,
                item.advance_refund_due,
                item.removed_from_operational_schedule,
            ),
        )
        cursor.execute(
            """
            insert into lending.loan_installment_operational_amounts (
                installment_id,
                operational_amount,
                operational_principal_component,
                operational_interest_component,
                removed_from_operational_schedule,
                last_extra_principal_adjustment_id,
                updated_by_user_id
            ) values (%s, %s, %s, %s, %s, %s, %s)
            on conflict (installment_id) do update
            set operational_amount = excluded.operational_amount,
                operational_principal_component =
                    excluded.operational_principal_component,
                operational_interest_component =
                    excluded.operational_interest_component,
                removed_from_operational_schedule =
                    excluded.removed_from_operational_schedule,
                last_extra_principal_adjustment_id =
                    excluded.last_extra_principal_adjustment_id,
                updated_by_user_id = excluded.updated_by_user_id,
                updated_at = now()
            """,
            (
                item.installment_id,
                item.operational_amount,
                item.operational_principal_component,
                new_interest,
                item.removed_from_operational_schedule,
                adjustment_id,
                actor_user_id,
            ),
        )
        if item.advance_refund_due > ZERO:
            cursor.execute(
                """
                insert into lending.loan_unused_advance_refund_dues (
                    adjustment_id, installment_id, amount_due
                ) values (%s, %s, %s)
                """,
                (
                    adjustment_id,
                    item.installment_id,
                    item.advance_refund_due,
                ),
            )

    cursor.execute(
        """
        update lending.loan_schedule_operational_state
        set operational_version = %s,
            updated_by_user_id = %s,
            updated_at = now()
        where schedule_id = %s
          and operational_version = %s
        """,
        (
            resulting_version,
            actor_user_id,
            locked.schedule_id,
            locked.expected_operational_version,
        ),
    )
    if cursor.rowcount != 1:
        raise ExtraPrincipalPostingRejected(
            "The 7x7 operational schedule changed during Extra Principal posting.",
            code="seven_by_seven_extra_principal_state_conflict",
        )

    retained_advance = money(
        sum((item.advance_retained for item in plan.installments), ZERO)
    )
    result_details = {
        "payment_allocation_intent": (
            PaymentAllocationIntent.EXTRA_AS_PRINCIPAL_REDUCTION.value
        ),
        "seven_by_seven_extra_principal_adjustment_id": str(adjustment_id),
        "principal_extra_amount": _money_text(plan.principal_reduction),
        "interest_contribution": "0.00",
        "resulting_future_principal": _money_text(plan.resulting_future_principal),
        "removed_future_interest": _money_text(plan.removed_future_interest),
        "retained_advance": _money_text(retained_advance),
        "refund_due": _money_text(plan.advance_refund_due),
        "resulting_operational_version": resulting_version,
        "operational_state_digest": operational_state_digest,
        "automatic_source_posting": False,
    }
    cursor.execute(
        """
        update lending.collection_transactions
        set details = coalesce(details, '{}'::jsonb) || %s
        where id = %s
          and is_voided = false
          and is_locked = false
        """,
        (Jsonb(result_details), transaction_id),
    )
    if cursor.rowcount != 1:
        raise ExtraPrincipalPostingRejected(
            "The 7x7 Extra Principal receipt became unavailable during posting.",
            code="seven_by_seven_extra_principal_receipt_mismatch",
        )

    cursor.execute(
        """
        insert into core.audit_logs (
            actor_user_id,
            action,
            target_type,
            target_id,
            details,
            created_at
        ) values (
            %s,
            'collection.7x7.extra_principal.recorded',
            'collection_transaction',
            %s,
            %s,
            now()
        )
        """,
        (
            actor_user_id,
            transaction_id,
            Jsonb(
                {
                    "loan_id": str(loan_id),
                    "schedule_id": str(locked.schedule_id),
                    "adjustment_id": str(adjustment_id),
                    **result_details,
                }
            ),
        ),
    )


def _posting_rejection(
    error: SevenBySevenExtraPrincipalError | SevenBySevenExtraPrincipalReplayError,
) -> ExtraPrincipalPostingRejected:
    return ExtraPrincipalPostingRejected(str(error), code=error.code)


def _money_text(value: Decimal) -> str:
    return format(money(value), ".2f")
