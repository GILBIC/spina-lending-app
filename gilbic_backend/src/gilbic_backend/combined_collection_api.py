from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from enum import Enum
from typing import Annotated, Any
from uuid import UUID, uuid5

from fastapi import APIRouter, Depends, Header, HTTPException
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from spina_mobile_collections.contracts import (
    ActorContext,
    CollectionCommand,
    CollectionEntryType,
    PastDueFollowupInput,
    PastDueReasonCode,
    PaymentAllocationIntent,
)
from spina_mobile_collections.service import (
    CONTRACT_VERSION,
    CollectionConflict,
    CollectionRejected,
)

from .collection_api import collection_actor_dependency
from .concurrent_receipt_collection_posting import (
    ConcurrentReceiptSafeCollectionPostingBridge,
)
from .database import connect_database
from .seven_by_seven_advance_activation import (
    SevenBySevenAdvanceActivationError,
    replay_verified_seven_by_seven_financial_state,
)
from .seven_by_seven_operational_allocator import (
    SevenBySevenAllocationError,
    SevenBySevenCashEvent,
    allocate_seven_by_seven_payments,
)

MONEY = Decimal("0.01")
ZERO = Decimal("0.00")
PHILIPPINES_TIMEZONE = timezone(timedelta(hours=8), name="Asia/Manila")


class CombinedExtraAllocationChoice(str, Enum):
    SEVEN_BY_SEVEN_ADVANCE = "seven_by_seven_advance"
    SEVEN_BY_SEVEN_EXTRA_PRINCIPAL = "seven_by_seven_extra_principal"
    REGULAR_ADVANCE = "regular_advance"
    REGULAR_PRINCIPAL_REDUCTION = "regular_principal_reduction"


@dataclass(frozen=True, slots=True)
class CombinedAllocationPlan:
    cash_received: Decimal
    seven_by_seven_collectible: Decimal
    regular_collectible: Decimal
    seven_by_seven_scheduled: Decimal
    regular_scheduled: Decimal
    extra_amount: Decimal
    extra_choice: CombinedExtraAllocationChoice | None
    status: str
    requires_review: bool


def _money(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def _plan_combined_allocation(
    *,
    cash_received: Decimal | int | str,
    seven_by_seven_collectible: Decimal | int | str,
    regular_collectible: Decimal | int | str,
    extra_choice: CombinedExtraAllocationChoice | None = None,
) -> CombinedAllocationPlan:
    """Allocate one physical receipt using Management's frozen order.

    Ordinary cash clears every collectible 7x7 obligation first, then Regular.
    Any remainder after both loan obligations are current remains a true extra
    whose borrower direction must be preserved explicitly.
    """

    cash = _money(cash_received)
    seven_due = _money(seven_by_seven_collectible)
    regular_due = _money(regular_collectible)
    if cash <= ZERO:
        raise ValueError("Cash received must be greater than zero.")
    if seven_due < ZERO or regular_due < ZERO:
        raise ValueError("Collectible obligations cannot be negative.")

    seven_scheduled = min(cash, seven_due)
    after_seven = _money(cash - seven_scheduled)
    regular_scheduled = min(after_seven, regular_due)
    extra = _money(after_seven - regular_scheduled)
    total_due = _money(seven_due + regular_due)

    if extra > ZERO and extra_choice is None:
        status = "extra_choice_required"
    elif extra > ZERO:
        status = "excess"
    elif cash < total_due:
        status = "short"
    else:
        status = "exact"

    return CombinedAllocationPlan(
        cash_received=cash,
        seven_by_seven_collectible=seven_due,
        regular_collectible=regular_due,
        seven_by_seven_scheduled=_money(seven_scheduled),
        regular_scheduled=_money(regular_scheduled),
        extra_amount=extra,
        extra_choice=extra_choice,
        status=status,
        requires_review=status != "exact",
    )


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CombinedPaymentLeg(_StrictModel):
    route_entry_id: UUID
    loan_id: UUID
    route_revision: str = Field(min_length=1, max_length=200)
    legacy_amount: Decimal | None = Field(
        default=None,
        alias="amount",
        exclude=True,
        gt=ZERO,
        max_digits=18,
        decimal_places=2,
    )


class CombinedPastDueFollowup(_StrictModel):
    reason_code: PastDueReasonCode
    note: str = Field(default="", max_length=500)
    promised_payment_date: date | None = None
    promised_amount: Decimal | None = Field(
        default=None,
        gt=ZERO,
        max_digits=18,
        decimal_places=2,
    )

    @model_validator(mode="after")
    def validate_details(self) -> CombinedPastDueFollowup:
        note = self.note.strip()
        if self.reason_code is PastDueReasonCode.OTHER and not note:
            raise ValueError("Other Past Due reason requires a short explanation.")
        is_promise = self.reason_code is PastDueReasonCode.PROMISED_TO_PAY_LATER
        if is_promise:
            if self.promised_payment_date is None or self.promised_amount is None:
                raise ValueError(
                    "Promised to pay later requires a promised payment date and amount."
                )
        elif self.promised_payment_date is not None or self.promised_amount is not None:
            raise ValueError(
                "Promise date and amount are only valid for Promised to pay later."
            )
        return self

    def to_input(self) -> PastDueFollowupInput:
        return PastDueFollowupInput(
            reason_code=self.reason_code,
            note=self.note.strip(),
            promised_payment_date=self.promised_payment_date,
            promised_amount=self.promised_amount,
        )


class CombinedPaymentRequest(_StrictModel):
    client_transaction_id: UUID
    client_id: UUID
    collection_date: date
    recorded_at: datetime
    device_id: str = Field(min_length=1, max_length=500)
    device_sequence: int = Field(ge=1)
    cash_received_amount: Decimal = Field(
        gt=0,
        max_digits=18,
        decimal_places=2,
    )
    extra_allocation_choice: CombinedExtraAllocationChoice | None = None
    regular_past_due_followup: CombinedPastDueFollowup | None = None
    reviewed_allocation_hash: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )
    legs: list[CombinedPaymentLeg] = Field(min_length=2, max_length=2)

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_exact_total(cls, value: Any) -> Any:
        """Preserve the prior exact one-tap body without trusting its split.

        The previous mobile contract sent one positive amount on each leg. Its
        total is safe to preserve during rollout because the server discards
        that proposed split, recomputes both collectible obligations, and still
        rejects short/excess cash without the new review evidence.
        """

        if not isinstance(value, dict):
            return value
        raw_legs = value.get("legs")
        contains_legacy_amount = isinstance(raw_legs, list) and any(
            isinstance(leg, dict) and "amount" in leg for leg in raw_legs
        )
        if "cash_received_amount" in value:
            if contains_legacy_amount:
                raise ValueError(
                    "Do not mix cash_received_amount with legacy per-loan amounts."
                )
            return value
        if (
            not isinstance(raw_legs, list)
            or len(raw_legs) != 2
            or any(not isinstance(leg, dict) or "amount" not in leg for leg in raw_legs)
        ):
            return value

        legacy_amounts: list[Decimal] = []
        try:
            for leg in raw_legs:
                amount = Decimal(str(leg["amount"]))
                if (
                    not amount.is_finite()
                    or amount <= ZERO
                    or amount.as_tuple().exponent < -2
                    or len(amount.as_tuple().digits) > 18
                ):
                    raise ValueError
                legacy_amounts.append(amount)
        except (InvalidOperation, ValueError) as error:
            raise ValueError(
                "Legacy combined payment amounts must be positive money values."
            ) from error

        normalized = dict(value)
        normalized["cash_received_amount"] = sum(legacy_amounts, ZERO)
        return normalized

    @field_validator("recorded_at")
    @classmethod
    def recorded_at_requires_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("recorded_at must include a timezone")
        return value

    @field_validator("legs")
    @classmethod
    def legs_must_be_unique(cls, value: list[CombinedPaymentLeg]):
        loan_ids = [item.loan_id for item in value]
        if len(set(loan_ids)) != len(loan_ids):
            raise ValueError("Combined payment legs must reference different loans.")
        return value


def _canonical_payload(body: CombinedPaymentRequest) -> dict[str, Any]:
    return {
        "client_transaction_id": str(body.client_transaction_id),
        "client_id": str(body.client_id),
        "collection_date": body.collection_date.isoformat(),
        "recorded_at": body.recorded_at.isoformat(),
        "device_id": body.device_id,
        "device_sequence": body.device_sequence,
        "cash_received_amount": format(body.cash_received_amount, "f"),
        "extra_allocation_choice": (
            body.extra_allocation_choice.value
            if body.extra_allocation_choice is not None
            else None
        ),
        "regular_past_due_followup": (
            body.regular_past_due_followup.to_input().canonical_payload()
            if body.regular_past_due_followup is not None
            else None
        ),
        "reviewed_allocation_hash": body.reviewed_allocation_hash,
        "legs": [
            {
                "route_entry_id": str(leg.route_entry_id),
                "loan_id": str(leg.loan_id),
                "route_revision": leg.route_revision.strip(),
            }
            for leg in body.legs
        ],
    }


def _legacy_canonical_payload(body: CombinedPaymentRequest) -> dict[str, Any] | None:
    """Rebuild the exact pre-one-total hash for uncertain legacy retries."""

    if (
        body.extra_allocation_choice is not None
        or body.regular_past_due_followup is not None
        or body.reviewed_allocation_hash is not None
        or any(leg.legacy_amount is None for leg in body.legs)
    ):
        return None
    return {
        "client_transaction_id": str(body.client_transaction_id),
        "client_id": str(body.client_id),
        "collection_date": body.collection_date.isoformat(),
        "recorded_at": body.recorded_at.isoformat(),
        "device_id": body.device_id,
        "device_sequence": body.device_sequence,
        "legs": [
            {
                "route_entry_id": str(leg.route_entry_id),
                "loan_id": str(leg.loan_id),
                "route_revision": leg.route_revision.strip(),
                "amount": format(leg.legacy_amount, "f"),
            }
            for leg in body.legs
        ],
    }


def _hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_regular_plus_7x7(
    connection,
    body: CombinedPaymentRequest,
    *,
    collector_account_id: UUID,
) -> dict[str, dict[str, Any]]:
    loan_ids = [leg.loan_id for leg in body.legs]
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            select
                loan.id,
                loan.client_id,
                loan.status,
                loan.principal,
                loan.daily_amount,
                loan.date_released,
                loan_type.daily_interest_per_1000,
                loan_type.calculation_mode,
                loan_type.settings,
                client.status as client_status,
                coalesce(state.remaining_balance, loan.principal) as remaining_balance,
                coalesce(state.is_reconciled, false) as is_reconciled,
                coalesce(state.state_version, 0) as state_version
            from lending.loans loan
            join lending.loan_types loan_type on loan_type.id = loan.loan_type_id
            join lending.clients client on client.id = loan.client_id
            left join lending.loan_collection_state state on state.loan_id = loan.id
            where loan.id = any(%s)
              and exists (
                  select 1
                  from lending.collector_area_assignments assignment
                  where assignment.collector_user_id = %s
                    and assignment.is_active = true
                    and lending.area_path_contains(
                        assignment.area,
                        coalesce(client.area, ''),
                        true
                    )
              )
            order by loan.id
            for update of loan
            """,
            (loan_ids, collector_account_id),
        )
        rows = cursor.fetchall()
    if len(rows) != 2:
        raise CollectionRejected(
            "Combined Pay is only available for both loans on this collector's assigned route.",
            code="combined_route_not_assigned",
        )
    if any(row["client_id"] != body.client_id for row in rows):
        raise CollectionRejected(
            "Combined payment loans must belong to the same client.",
            code="combined_client_mismatch",
        )

    leg_by_loan = {leg.loan_id: leg for leg in body.legs}
    for row in rows:
        leg = leg_by_loan[row["id"]]
        if leg.route_entry_id != leg.loan_id:
            raise CollectionRejected(
                "A combined route entry no longer matches its loan. Refresh the route.",
                code="combined_route_entry_changed",
            )
        expected_version = (
            ConcurrentReceiptSafeCollectionPostingBridge._route_revision_state_version(
                route_revision=leg.route_revision,
                loan_id=leg.loan_id,
            )
        )
        current_version = int(row["state_version"])
        route_is_safe = expected_version == current_version
        if expected_version is not None and expected_version < current_version:
            with connection.cursor(row_factory=dict_row) as cursor:
                route_is_safe = ConcurrentReceiptSafeCollectionPostingBridge._same_day_payment_revision_chain_is_safe(
                    cursor,
                    loan_id=leg.loan_id,
                    collection_date=body.collection_date,
                    expected_version=expected_version,
                    current_version=current_version,
                )
        if not route_is_safe:
            raise CollectionRejected(
                "A combined loan changed after this route was loaded. Refresh the route.",
                code="combined_route_revision_changed",
            )

        settings = row["settings"] if isinstance(row["settings"], dict) else {}
        mobile_enabled = str(settings.get("mobile_collections_enabled") or "").strip().lower() in {
            "true",
            "1",
            "yes",
            "on",
        }
        mode = str(row["calculation_mode"] or "").strip().lower()
        seven_enabled = str(settings.get("mobile_seven_by_seven_enabled") or "").strip().lower() in {
            "true",
            "1",
            "yes",
            "on",
        }
        if (
            str(row["status"]) != "active"
            or str(row["client_status"]) != "active"
            or not bool(row["is_reconciled"])
            or not mobile_enabled
            or str(settings.get("mobile_balance_mode") or "").strip()
            != "direct_remaining_balance"
            or (mode == "seven_by_seven" and not seven_enabled)
        ):
            raise CollectionRejected(
                "Combined Pay is unavailable because a client or loan is not ready for protected mobile collection.",
                code="combined_collection_not_ready",
            )

    modes = sorted(str(row["calculation_mode"] or "").strip().lower() for row in rows)
    if modes != ["fixed_daily", "seven_by_seven"]:
        raise CollectionRejected(
            "One-tap combined Pay is limited to exactly one Regular loan and one 7x7 loan.",
            code="combined_regular_7x7_required",
        )
    return {str(row["calculation_mode"] or "").strip().lower(): row for row in rows}


def _lock_combined_preflight(
    connection,
    *,
    body: CombinedPaymentRequest,
    actor: ActorContext,
    reserve_device_sequences: bool,
) -> None:
    """Acquire the official posting locks before any loan row is locked."""

    bridge = ConcurrentReceiptSafeCollectionPostingBridge()
    registered_device_id = UUID(actor.storage_device_id)
    with connection.cursor(row_factory=dict_row) as cursor:
        if reserve_device_sequences:
            for offset in range(3):
                bridge._lock_device_sequence(
                    cursor,
                    registered_device_id=registered_device_id,
                    device_sequence=body.device_sequence + offset,
                )
        for loan_id in sorted((leg.loan_id for leg in body.legs), key=str):
            bridge._lock_loan_date(
                cursor,
                loan_id=loan_id,
                collection_date=body.collection_date,
            )
        bridge._verify_device(
            cursor,
            collector_user_id=UUID(actor.account_id),
            registered_device_id=registered_device_id,
        )


def _require_regular_schedule_posting_ready(
    connection,
    *,
    loan: dict[str, Any],
    schedule_id: UUID,
) -> None:
    """Keep combined preview on the same protected Regular gate as posting."""

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            select
                lower(coalesce(loan_type.settings->>'mobile_collections_enabled', ''))
                    in ('true', '1', 'yes', 'on') as mobile_collections_enabled,
                coalesce(loan_type.settings->>'mobile_balance_mode', '')
                    as mobile_balance_mode,
                coalesce(state.is_reconciled, false) as collection_state_reconciled,
                assessment.schedule_id,
                assessment.dpd_data_status,
                assessment.contractual_schedule_total,
                assessment.allocated_schedule_total,
                assessment.automatic_default_label_written,
                assessment.ecl_included,
                assessment.ecl_amount,
                assessment.ready_to_post,
                registration.id as registration_id,
                coalesce(activation.event_action, '') as activation_action,
                activation.schedule_id as activation_schedule_id
            from lending.loans loan
            join lending.loan_types loan_type on loan_type.id = loan.loan_type_id
            left join lending.loan_collection_state state on state.loan_id = loan.id
            left join accounting.loan_contract_dpd_assessment assessment
              on assessment.loan_id = loan.id
             and assessment.schedule_id = %s
            left join lending.loan_contract_schedule_registrations registration
              on registration.schedule_id = assessment.schedule_id
            left join lending.loan_contract_collection_activation_state activation
              on activation.loan_id = loan.id
            where loan.id = %s
            """,
            (schedule_id, loan["id"]),
        )
        gate = cursor.fetchone()

    ready = (
        gate is not None
        and bool(gate["mobile_collections_enabled"])
        and str(gate["mobile_balance_mode"]) == "direct_remaining_balance"
        and bool(gate["collection_state_reconciled"])
        and gate["schedule_id"] == schedule_id
        and gate["registration_id"] is not None
        and str(gate["dpd_data_status"]) == "ready"
        and not bool(gate["automatic_default_label_written"])
        and not bool(gate["ecl_included"])
        and gate["ecl_amount"] is None
        and not bool(gate["ready_to_post"])
        and str(gate["activation_action"]) == "activate"
        and gate["activation_schedule_id"] == schedule_id
    )
    if ready:
        unpaid = _money(
            Decimal(gate["contractual_schedule_total"])
            - Decimal(gate["allocated_schedule_total"])
        )
        ready = unpaid == _money(loan["remaining_balance"])
    if not ready:
        raise CollectionRejected(
            "The Regular signed schedule is not ready for protected combined allocation. Ask Management to reconcile and activate it.",
            code="combined_regular_contract_schedule_not_ready",
        )


def _collectible_obligation(
    connection,
    *,
    loan: dict[str, Any],
    collection_date: date,
) -> tuple[Decimal, str]:
    """Read the amount collectible through the receipt date from server state."""

    mode = str(loan["calculation_mode"] or "").strip().lower()
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            with registered_schedule_history as (
                select schedule.id
                from lending.loan_contract_schedules schedule
                join lending.loan_contract_schedule_registrations registration
                  on registration.schedule_id = schedule.id
                where schedule.loan_id = %s
            ), active_schedule as (
                select schedule.id
                from lending.loan_contract_schedules schedule
                join lending.loan_contract_schedule_registrations registration
                  on registration.schedule_id = schedule.id
                where schedule.loan_id = %s
                  and schedule.status = 'active'
            ), allocated as (
                select
                    allocation.installment_id,
                    coalesce(sum(allocation.amount_applied) filter (
                        where transaction.is_voided = false
                          and (
                              %s <> 'seven_by_seven'
                              or allocation.allocation_basis <> 'future_advance_oldest_first'
                          )
                    ), 0)::numeric(18,2) as directly_allocated
                from lending.loan_installment_payment_allocations allocation
                join lending.loan_contract_installments_operational installment_scope
                  on installment_scope.id = allocation.installment_id
                join active_schedule schedule_scope
                  on schedule_scope.id = installment_scope.schedule_id
                join lending.collection_transactions transaction
                  on transaction.id = allocation.transaction_id
                group by allocation.installment_id
            )
            select
                (select min(id::text)::uuid from active_schedule) as schedule_id,
                (select count(*) from registered_schedule_history)::integer
                    as registration_count,
                count(distinct schedule.id)::integer as schedule_count,
                count(installment.id)::integer as installment_count,
                coalesce(sum(greatest(
                    installment.operational_amount
                    - coalesce(allocated.directly_allocated, 0)
                    - case
                        when %s = 'seven_by_seven'
                            then coalesce(active_advance.active_advance_allocated, 0)
                        else 0
                      end,
                    0
                )), 0)::numeric(18,2) as collectible_amount
            from active_schedule schedule
            left join lending.loan_contract_installments_operational installment
              on installment.schedule_id = schedule.id
             and installment.effective_due_date <= %s
             and installment.removed_from_operational_schedule = false
            left join allocated on allocated.installment_id = installment.id
            left join lending.loan_installment_active_advance active_advance
              on active_advance.installment_id = installment.id
            """,
            (loan["id"], loan["id"], mode, mode, collection_date),
        )
        schedule = cursor.fetchone()
        schedule_count = int(schedule["schedule_count"] or 0) if schedule else 0
        registration_count = (
            int(schedule["registration_count"] or 0) if schedule else 0
        )
        if schedule_count == 1:
            if mode == "fixed_daily":
                _require_regular_schedule_posting_ready(
                    connection,
                    loan=loan,
                    schedule_id=schedule["schedule_id"],
                )
            return _money(schedule["collectible_amount"]), "verified_schedule"
        if registration_count > 0:
            raise CollectionRejected(
                "The loan has signed-schedule history but no single active verified schedule. Ask Management to reconcile it before combined Pay.",
                code="combined_active_schedule_required",
            )

        # Transitional loans without registered signed schedules still use the
        # server's official daily amount. Same-day receipts are subtracted so a
        # stale client cannot recreate today's obligation.
        cursor.execute(
            """
            select coalesce(sum(transaction.applied_amount), 0)::numeric(18,2)
                as paid_today
            from lending.collection_transactions transaction
            where transaction.loan_id = %s
              and transaction.collection_date = %s
              and transaction.entry_type = 'payment'
              and transaction.is_voided = false
            """,
            (loan["id"], collection_date),
        )
        paid_today_row = cursor.fetchone()

    daily = _money(loan["daily_amount"])
    balance = _money(loan["remaining_balance"])
    paid_today = _money(
        paid_today_row["paid_today"] if paid_today_row is not None else ZERO
    )
    remaining_daily = _money(max(daily - paid_today, ZERO))
    collectible = _money(min(remaining_daily, balance))
    return collectible, "server_daily_fallback"


def _authoritative_allocation_evidence(
    connection,
    *,
    loan: dict[str, Any],
) -> dict[str, Any]:
    """Fingerprint the exact schedule/operational rows behind a reviewed split."""

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            with active_schedule as (
                select schedule.id, schedule.schedule_version
                from lending.loan_contract_schedules schedule
                join lending.loan_contract_schedule_registrations registration
                  on registration.schedule_id = schedule.id
                where schedule.loan_id = %s
                  and schedule.status = 'active'
            )
            select
                schedule.id as schedule_id,
                schedule.schedule_version,
                coalesce(operational.operational_version, 0)
                    as operational_version,
                installment.id as installment_id,
                installment.installment_number,
                installment.effective_due_date,
                installment.operational_amount,
                installment.removed_from_operational_schedule,
                coalesce(sum(allocation.amount_applied) filter (
                    where transaction.is_voided = false
                ), 0)::numeric(18,2) as allocated_amount,
                coalesce(active_advance.active_advance_allocated, 0)
                    ::numeric(18,2) as active_advance_amount
            from active_schedule schedule
            left join lending.loan_schedule_operational_state operational
              on operational.schedule_id = schedule.id
            left join lending.loan_contract_installments_operational installment
              on installment.schedule_id = schedule.id
            left join lending.loan_installment_payment_allocations allocation
              on allocation.installment_id = installment.id
            left join lending.collection_transactions transaction
              on transaction.id = allocation.transaction_id
            left join lending.loan_installment_active_advance active_advance
              on active_advance.installment_id = installment.id
            group by
                schedule.id,
                schedule.schedule_version,
                operational.operational_version,
                installment.id,
                installment.installment_number,
                installment.effective_due_date,
                installment.operational_amount,
                installment.removed_from_operational_schedule,
                active_advance.active_advance_allocated
            order by installment.installment_number, installment.id
            """,
            (loan["id"],),
        )
        rows = cursor.fetchall()

    if not rows:
        return {
            "basis": "server_daily_fallback",
            "state_version": int(loan["state_version"]),
            "daily_amount": format(_money(loan["daily_amount"]), "f"),
            "remaining_balance": format(_money(loan["remaining_balance"]), "f"),
        }

    installments = [
        {
            "installment_id": int(row["installment_id"]),
            "installment_number": int(row["installment_number"]),
            "effective_due_date": row["effective_due_date"].isoformat(),
            "operational_amount": format(_money(row["operational_amount"]), "f"),
            "removed": bool(row["removed_from_operational_schedule"]),
            "allocated_amount": format(_money(row["allocated_amount"]), "f"),
            "active_advance_amount": format(
                _money(row["active_advance_amount"]), "f"
            ),
        }
        for row in rows
        if row["installment_id"] is not None
    ]
    first = rows[0]
    return {
        "basis": "verified_schedule",
        "schedule_id": str(first["schedule_id"]),
        "schedule_version": int(first["schedule_version"]),
        "operational_version": int(first["operational_version"]),
        "installment_state_digest": _hash({"installments": installments}),
    }


def _project_seven_by_seven_cash(
    connection,
    *,
    loan: dict[str, Any],
    collection_date: date,
    scheduled_amount: Decimal,
    extra_amount: Decimal,
    extra_choice: CombinedExtraAllocationChoice | None,
) -> dict[str, Any]:
    """Run the protected interest-first allocator without writing a receipt."""

    with connection.cursor(row_factory=dict_row) as cursor:
        payment_start = loan["date_released"] + timedelta(days=1)
        cursor.execute(
            """
            select max(transaction.collection_date) as financial_watermark
            from lending.collection_transactions transaction
            where transaction.loan_id = %s
              and transaction.is_voided = false
              and transaction.amount > 0
              and transaction.entry_type in ('payment', 'advance')
            """,
            (loan["id"],),
        )
        watermark_row = cursor.fetchone()
        watermark = watermark_row["financial_watermark"] if watermark_row else None
        if watermark is not None and collection_date < watermark:
            raise CollectionRejected(
                "A 7x7 collection cannot be previewed before the latest accepted financial receipt date.",
                code="seven_by_seven_advance_activation_conflict",
            )
        baseline_date = watermark or (payment_start - timedelta(days=1))
        try:
            baseline = replay_verified_seven_by_seven_financial_state(
                cursor,
                loan_id=loan["id"],
                original_principal=_money(loan["principal"]),
                daily_interest_per_1000=_money(loan["daily_interest_per_1000"]),
                payment_start=payment_start,
                through_date=baseline_date,
            )
            historical = replay_verified_seven_by_seven_financial_state(
                cursor,
                loan_id=loan["id"],
                original_principal=_money(loan["principal"]),
                daily_interest_per_1000=_money(loan["daily_interest_per_1000"]),
                payment_start=payment_start,
                through_date=collection_date,
            )
        except SevenBySevenAdvanceActivationError as error:
            raise CollectionRejected(str(error), code=error.code) from error

        stored_balance = _money(loan["remaining_balance"])
        if baseline.result.closing_remaining_principal != stored_balance:
            raise CollectionRejected(
                "The 7x7 balance does not match its protected financial watermark. Ask Management to reconcile it.",
                code="seven_by_seven_balance_not_reconciled",
            )
        if historical.result.closing_remaining_principal > stored_balance:
            raise CollectionRejected(
                "7x7 prepayment activation would increase principal. Ask Management to reconcile it.",
                code="seven_by_seven_advance_activation_conflict",
            )

        projected_events = list(historical.historical_events)
        projection: dict[str, Any] = {}
        for component, amount in (
            ("scheduled", scheduled_amount),
            ("extra", extra_amount),
        ):
            if amount <= ZERO:
                continue
            if (
                component == "extra"
                and extra_choice
                is CombinedExtraAllocationChoice.SEVEN_BY_SEVEN_ADVANCE
            ):
                projection[component] = {
                    "cash_amount": format(_money(amount), "f"),
                    "financial_state": "deferred_until_effective_due_date",
                    "interest_paid": "0.00",
                    "principal_paid": "0.00",
                    "closing_principal": projection.get("scheduled", {}).get(
                        "closing_principal",
                        format(_money(loan["remaining_balance"]), "f"),
                    ),
                }
                continue
            projected_events.append(
                SevenBySevenCashEvent(
                    event_id=f"combined-preview:{component}",
                    collection_date=collection_date,
                    amount=_money(amount),
                )
            )
            try:
                result = allocate_seven_by_seven_payments(
                    original_principal=_money(loan["principal"]),
                    daily_interest_per_1000=_money(
                        loan["daily_interest_per_1000"]
                    ),
                    payment_start=payment_start,
                    events=tuple(projected_events),
                    interest_holiday_dates=historical.interest_holiday_dates,
                )
            except SevenBySevenAllocationError as error:
                raise CollectionRejected(
                    "The 7x7 cash cannot be projected through the protected interest-first allocator.",
                    code="seven_by_seven_allocation_conflict",
                ) from error
            line = result.allocations[-1]
            if line.unallocated_cash > ZERO:
                raise CollectionRejected(
                    "The 7x7 amount is above the exact protected payoff for this date.",
                    code="combined_amount_exceeds_payoff",
                )
            if (
                component == "extra"
                and extra_choice
                is CombinedExtraAllocationChoice.SEVEN_BY_SEVEN_EXTRA_PRINCIPAL
                and (
                    line.interest_due != ZERO
                    or line.interest_paid != ZERO
                    or line.principal_paid != _money(amount)
                )
            ):
                raise CollectionRejected(
                    "Past Due Interest and Today Interest must be fully paid before 7x7 Extra Principal.",
                    code="seven_by_seven_extra_principal_interest_outstanding",
                )
            projection[component] = {
                "cash_amount": format(_money(amount), "f"),
                "interest_paid": format(_money(line.interest_paid), "f"),
                "principal_paid": format(_money(line.principal_paid), "f"),
                "closing_principal": format(
                    _money(line.closing_remaining_principal), "f"
                ),
            }
        return projection


def _allocation_preview(
    connection,
    body: CombinedPaymentRequest,
    *,
    collector_account_id: UUID,
) -> dict[str, Any]:
    loans = _validate_regular_plus_7x7(
        connection,
        body,
        collector_account_id=collector_account_id,
    )
    regular = loans["fixed_daily"]
    seven = loans["seven_by_seven"]
    regular_due, regular_basis = _collectible_obligation(
        connection,
        loan=regular,
        collection_date=body.collection_date,
    )
    seven_due, seven_basis = _collectible_obligation(
        connection,
        loan=seven,
        collection_date=body.collection_date,
    )
    if regular_due <= ZERO or seven_due <= ZERO:
        raise CollectionRejected(
            "Combined Pay requires collectible obligations on both the Regular and 7x7 loans. Refresh the route and review this client.",
            code="combined_obligation_changed",
        )

    plan = _plan_combined_allocation(
        cash_received=body.cash_received_amount,
        seven_by_seven_collectible=seven_due,
        regular_collectible=regular_due,
        extra_choice=body.extra_allocation_choice,
    )
    if plan.extra_amount == ZERO and body.extra_allocation_choice is not None:
        raise CollectionRejected(
            "The cash received does not include a true extra amount, so an extra allocation choice is not needed.",
            code="combined_extra_allocation_choice_not_needed",
        )
    if (
        plan.extra_amount > ZERO
        and body.extra_allocation_choice
        in {
            CombinedExtraAllocationChoice.REGULAR_ADVANCE,
            CombinedExtraAllocationChoice.REGULAR_PRINCIPAL_REDUCTION,
        }
        and regular_basis != "verified_schedule"
    ):
        raise CollectionRejected(
            "Regular Advance or Principal Reduction requires an activated verified signed schedule.",
            code="combined_regular_extra_schedule_required",
        )
    leg_by_loan = {leg.loan_id: leg for leg in body.legs}
    regular_leg = leg_by_loan[regular["id"]]
    seven_leg = leg_by_loan[seven["id"]]

    regular_extra = (
        plan.extra_amount
        if plan.extra_choice
        in {
            CombinedExtraAllocationChoice.REGULAR_ADVANCE,
            CombinedExtraAllocationChoice.REGULAR_PRINCIPAL_REDUCTION,
        }
        else ZERO
    )
    seven_extra = (
        plan.extra_amount
        if plan.extra_choice
        in {
            CombinedExtraAllocationChoice.SEVEN_BY_SEVEN_ADVANCE,
            CombinedExtraAllocationChoice.SEVEN_BY_SEVEN_EXTRA_PRINCIPAL,
        }
        else ZERO
    )
    if _money(plan.regular_scheduled + regular_extra) > _money(
        regular["remaining_balance"]
    ):
        raise CollectionRejected(
            "The Regular allocation exceeds the exact remaining payoff. Refresh and review the physical cash received.",
            code="combined_amount_exceeds_payoff",
        )
    if seven_extra > ZERO and seven_basis != "verified_schedule":
        raise CollectionRejected(
            "7x7 Advance or Extra Principal requires an active verified signed schedule.",
            code="combined_seven_by_seven_extra_schedule_required",
        )
    seven_advance_dates: tuple[date, ...] = ()
    if (
        plan.extra_choice is CombinedExtraAllocationChoice.SEVEN_BY_SEVEN_ADVANCE
        and seven_extra > ZERO
    ):
        seven_advance_dates = _seven_by_seven_advance_dates(
            connection,
            loan_id=seven["id"],
            collection_date=body.collection_date,
            amount=seven_extra,
        )
    seven_cash_projection = _project_seven_by_seven_cash(
        connection,
        loan=seven,
        collection_date=body.collection_date,
        scheduled_amount=plan.seven_by_seven_scheduled,
        extra_amount=seven_extra,
        extra_choice=plan.extra_choice,
    )
    regular_evidence = _authoritative_allocation_evidence(connection, loan=regular)
    seven_evidence = _authoritative_allocation_evidence(connection, loan=seven)
    review_evidence = {
        "client_transaction_id": str(body.client_transaction_id),
        "client_id": str(body.client_id),
        "collection_date": body.collection_date.isoformat(),
        "cash_received_amount": format(plan.cash_received, "f"),
        "extra_allocation_choice": (
            plan.extra_choice.value if plan.extra_choice is not None else None
        ),
        "loans": [
            {
                "loan_id": str(seven["id"]),
                "route_revision": seven_leg.route_revision.strip(),
                "collectible_amount": format(seven_due, "f"),
                "collectible_basis": seven_basis,
                "scheduled_amount": format(plan.seven_by_seven_scheduled, "f"),
                "extra_amount": format(seven_extra, "f"),
                "projected_covered_dates": [
                    value.isoformat() for value in seven_advance_dates
                ],
                "authoritative_evidence": seven_evidence,
                "cash_projection": seven_cash_projection,
            },
            {
                "loan_id": str(regular["id"]),
                "route_revision": regular_leg.route_revision.strip(),
                "collectible_amount": format(regular_due, "f"),
                "collectible_basis": regular_basis,
                "scheduled_amount": format(plan.regular_scheduled, "f"),
                "extra_amount": format(regular_extra, "f"),
                "projected_covered_dates": [],
                "authoritative_evidence": regular_evidence,
            },
        ],
    }
    allocation_hash = _hash(review_evidence)
    expected = _money(seven_due + regular_due)
    short_amount = _money(max(expected - plan.cash_received, ZERO))
    regular_past_due_followup_required = (
        plan.regular_scheduled > ZERO
        and plan.regular_scheduled < plan.regular_collectible
    )

    if plan.status == "exact":
        message = (
            "Exact Regular + 7x7 amount. The server will save both receipts atomically."
        )
    elif plan.status == "short":
        message = "Short payment: collectible 7x7 is allocated first, then Regular. Review before saving."
    elif plan.status == "extra_choice_required":
        message = "Cash exceeds both collectible obligations. Record the borrower's Advance or Principal Reduction choice."
    else:
        message = "The scheduled obligations and borrower-directed extra allocation require review before saving."

    return {
        "status": plan.status,
        "requires_review": plan.requires_review,
        "allocation_hash": allocation_hash,
        "cash_received_amount": format(plan.cash_received, "f"),
        "expected_total_amount": format(expected, "f"),
        "short_amount": format(short_amount, "f"),
        "extra_amount": format(plan.extra_amount, "f"),
        "extra_allocation_choice": (
            plan.extra_choice.value if plan.extra_choice is not None else None
        ),
        "extra_choice_required": plan.status == "extra_choice_required",
        "regular_past_due_followup_required": regular_past_due_followup_required,
        "allocation_order": ["seven_by_seven", "regular"],
        "legs": [
            {
                "loan_id": str(seven["id"]),
                "route_entry_id": str(seven_leg.route_entry_id),
                "route_revision": seven_leg.route_revision.strip(),
                "loan_type": "seven_by_seven",
                "collectible_basis": seven_basis,
                "collectible_amount": format(seven_due, "f"),
                "scheduled_amount": format(plan.seven_by_seven_scheduled, "f"),
                "extra_amount": format(seven_extra, "f"),
                "projected_covered_dates": [
                    value.isoformat() for value in seven_advance_dates
                ],
                "authoritative_evidence": seven_evidence,
                "cash_projection": seven_cash_projection,
                "total_amount": format(
                    _money(plan.seven_by_seven_scheduled + seven_extra), "f"
                ),
            },
            {
                "loan_id": str(regular["id"]),
                "route_entry_id": str(regular_leg.route_entry_id),
                "route_revision": regular_leg.route_revision.strip(),
                "loan_type": "regular",
                "collectible_basis": regular_basis,
                "collectible_amount": format(regular_due, "f"),
                "scheduled_amount": format(plan.regular_scheduled, "f"),
                "extra_amount": format(regular_extra, "f"),
                "projected_covered_dates": [],
                "authoritative_evidence": regular_evidence,
                "total_amount": format(
                    _money(plan.regular_scheduled + regular_extra), "f"
                ),
            },
        ],
        "message": message,
    }


def _seven_by_seven_advance_dates(
    connection,
    *,
    loan_id: UUID,
    collection_date: date,
    amount: Decimal,
) -> tuple[date, ...]:
    """Project the oldest future 7x7 rows used after scheduled cash clears due rows."""

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            with active_schedule as (
                select schedule.id
                from lending.loan_contract_schedules schedule
                join lending.loan_contract_schedule_registrations registration
                  on registration.schedule_id = schedule.id
                where schedule.loan_id = %s
                  and schedule.status = 'active'
                order by registration.verified_at desc, schedule.schedule_version desc
                limit 1
            ), allocated as (
                select
                    allocation.installment_id,
                    coalesce(sum(allocation.amount_applied) filter (
                        where transaction.is_voided = false
                          and allocation.allocation_basis <> 'future_advance_oldest_first'
                    ), 0)::numeric(18,2) as directly_allocated
                from lending.loan_installment_payment_allocations allocation
                join lending.loan_contract_installments_operational installment_scope
                  on installment_scope.id = allocation.installment_id
                join active_schedule schedule_scope
                  on schedule_scope.id = installment_scope.schedule_id
                join lending.collection_transactions transaction
                  on transaction.id = allocation.transaction_id
                group by allocation.installment_id
            )
            select
                installment.effective_due_date,
                greatest(
                    installment.operational_amount
                    - coalesce(allocated.directly_allocated, 0)
                    - coalesce(active_advance.active_advance_allocated, 0),
                    0
                )::numeric(18,2) as remaining_amount
            from active_schedule schedule
            join lending.loan_contract_installments_operational installment
              on installment.schedule_id = schedule.id
            left join allocated on allocated.installment_id = installment.id
            left join lending.loan_installment_active_advance active_advance
              on active_advance.installment_id = installment.id
            where installment.effective_due_date > %s
              and installment.removed_from_operational_schedule = false
            order by installment.effective_due_date, installment.installment_number
            """,
            (loan_id, collection_date),
        )
        rows = cursor.fetchall()

    amount_left = _money(amount)
    covered: list[date] = []
    for row in rows:
        remaining = _money(row["remaining_amount"])
        if remaining <= ZERO:
            continue
        if amount_left <= ZERO:
            break
        covered.append(row["effective_due_date"])
        amount_left = _money(amount_left - min(amount_left, remaining))
    if amount_left != ZERO or not covered:
        raise CollectionRejected(
            "The selected 7x7 Advance exceeds the current future signed-schedule capacity.",
            code="seven_by_seven_advance_capacity_exceeded",
        )
    return tuple(covered)


def _validate_request_envelope(
    *,
    body: CombinedPaymentRequest,
    idempotency_key: UUID,
    client_transaction_id: UUID,
    contract_version: str,
    actor: ActorContext,
) -> None:
    if (
        idempotency_key != client_transaction_id
        or idempotency_key != body.client_transaction_id
    ):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "idempotency_key_mismatch",
                "message": "Combined collection transaction identifiers must match.",
            },
        )
    if contract_version != CONTRACT_VERSION:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "unsupported_contract_version",
                "message": "The Gilbic collection contract version is not supported.",
            },
        )
    if body.device_id.strip() != actor.device_id:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "device_not_registered",
                "message": "The registered device does not match this combined collection.",
            },
        )


def _current_business_date() -> date:
    return datetime.now(PHILIPPINES_TIMEZONE).date()


def _validate_current_route_date(collection_date: date) -> None:
    business_date = _current_business_date()
    if collection_date != business_date:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "combined_collection_date_changed",
                "message": (
                    "Combined Pay only accepts today's Philippine route date. "
                    "Refresh the collector route and try again."
                ),
                "expected_collection_date": business_date.isoformat(),
            },
        )


def _replay_or_conflict(
    row: dict[str, Any],
    *,
    actor: ActorContext,
    accepted_request_hashes: frozenset[str],
) -> dict[str, Any]:
    same_owner = (
        str(row["collector_account_id"]) == actor.account_id
        and str(row["registered_device_id"]) == actor.storage_device_id
    )
    if (
        not same_owner
        or str(row["canonical_request_hash"]) not in accepted_request_hashes
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "combined_idempotency_mismatch",
                "message": (
                    "This combined collection number was already used for different data. "
                    "Refresh the route and review the client."
                ),
            },
        )
    payload = dict(row["result_payload"] or {})
    payload["status"] = "duplicate"
    payload["duplicate"] = True
    payload["message"] = (
        "Already recorded. No duplicate Regular or 7x7 payment was created."
    )
    return payload


def create_combined_collection_router() -> APIRouter:
    router = APIRouter(tags=["collector-collections"])

    @router.post("/api/v1/collector/collections/combined/preview")
    @router.post(
        "/api/mobile/v1/collector/collections/combined/preview",
        include_in_schema=False,
    )
    def preview_combined_payment(
        body: CombinedPaymentRequest,
        idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
        client_transaction_id: Annotated[UUID, Header(alias="X-Client-Transaction-Id")],
        contract_version: Annotated[str, Header(alias="X-Gilbic-Contract-Version")],
        actor: Annotated[ActorContext, Depends(collection_actor_dependency)],
    ) -> dict[str, object]:
        _validate_request_envelope(
            body=body,
            idempotency_key=idempotency_key,
            client_transaction_id=client_transaction_id,
            contract_version=contract_version,
            actor=actor,
        )
        _validate_current_route_date(body.collection_date)
        try:
            with connect_database() as connection, connection.transaction():
                _lock_combined_preflight(
                    connection,
                    body=body,
                    actor=actor,
                    reserve_device_sequences=False,
                )
                preview = _allocation_preview(
                    connection,
                    body,
                    collector_account_id=UUID(actor.account_id),
                )
            return {"success": True, "data": preview}
        except CollectionRejected as error:
            raise HTTPException(
                status_code=422,
                detail={"code": error.code, "message": error.message},
            ) from error

    @router.post("/api/v1/collector/collections/combined")
    @router.post(
        "/api/mobile/v1/collector/collections/combined",
        include_in_schema=False,
    )
    def submit_combined_payment(
        body: CombinedPaymentRequest,
        idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
        client_transaction_id: Annotated[UUID, Header(alias="X-Client-Transaction-Id")],
        contract_version: Annotated[str, Header(alias="X-Gilbic-Contract-Version")],
        actor: Annotated[ActorContext, Depends(collection_actor_dependency)],
    ) -> dict[str, object]:
        _validate_request_envelope(
            body=body,
            idempotency_key=idempotency_key,
            client_transaction_id=client_transaction_id,
            contract_version=contract_version,
            actor=actor,
        )

        canonical = _canonical_payload(body)
        request_hash = _hash(canonical)
        legacy_canonical = _legacy_canonical_payload(body)
        accepted_request_hashes = frozenset(
            {
                request_hash,
                *(
                    (_hash(legacy_canonical),)
                    if legacy_canonical is not None
                    else ()
                ),
            }
        )
        bridge = ConcurrentReceiptSafeCollectionPostingBridge()
        try:
            with connect_database() as connection:  # noqa: SIM117
                with connection.transaction():
                    with connection.cursor(row_factory=dict_row) as cursor:
                        cursor.execute(
                            "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
                            (f"gilbic-combined:{idempotency_key}",),
                        )
                        cursor.execute(
                            """
                            select collector_account_id, registered_device_id,
                                   canonical_request_hash, result_payload
                            from mobile.gilbic_combined_collection_idempotency
                            where idempotency_key = %s
                            for update
                            """,
                            (idempotency_key,),
                        )
                        existing = cursor.fetchone()
                        if existing is not None:
                            return {
                                "success": True,
                                "data": _replay_or_conflict(
                                    existing,
                                    actor=actor,
                                    accepted_request_hashes=accepted_request_hashes,
                                ),
                            }

                    _validate_current_route_date(body.collection_date)
                    _lock_combined_preflight(
                        connection,
                        body=body,
                        actor=actor,
                        reserve_device_sequences=True,
                    )
                    preview = _allocation_preview(
                        connection,
                        body,
                        collector_account_id=UUID(actor.account_id),
                    )
                    if preview["extra_choice_required"]:
                        raise CollectionRejected(
                            "Cash exceeds both collectible obligations. Record the borrower's Advance or Principal Reduction choice before saving.",
                            code="combined_extra_allocation_choice_required",
                        )
                    if body.reviewed_allocation_hash is not None and (
                        body.reviewed_allocation_hash != preview["allocation_hash"]
                    ):
                        raise HTTPException(
                            status_code=409,
                            detail={
                                "code": "combined_allocation_review_required",
                                "message": (
                                    "The server allocation must be reviewed before this short or excess payment is saved."
                                ),
                                "preview": preview,
                            },
                        )
                    if (
                        preview["requires_review"]
                        and body.reviewed_allocation_hash is None
                    ):
                        raise HTTPException(
                            status_code=409,
                            detail={
                                "code": "combined_allocation_review_required",
                                "message": (
                                    "The server allocation must be reviewed before this short or excess payment is saved."
                                ),
                                "preview": preview,
                            },
                        )
                    if (
                        preview["regular_past_due_followup_required"]
                        and body.regular_past_due_followup is None
                    ):
                        raise CollectionRejected(
                            "This split leaves part of the Regular obligation unpaid. Choose the client's Past Due reason before saving.",
                            code="combined_regular_past_due_reason_required",
                        )
                    if (
                        not preview["regular_past_due_followup_required"]
                        and body.regular_past_due_followup is not None
                    ):
                        raise CollectionRejected(
                            "No partial Regular obligation remains, so a Regular Past Due reason is not needed.",
                            code="combined_regular_past_due_reason_not_needed",
                        )

                    preview_legs = {
                        str(item["loan_type"]): item for item in preview["legs"]
                    }
                    request_legs = {str(leg.loan_id): leg for leg in body.legs}
                    seven_preview = preview_legs["seven_by_seven"]
                    regular_preview = preview_legs["regular"]
                    seven_leg = request_legs[seven_preview["loan_id"]]
                    regular_leg = request_legs[regular_preview["loan_id"]]
                    seven_scheduled = _money(seven_preview["scheduled_amount"])
                    regular_scheduled = _money(regular_preview["scheduled_amount"])
                    seven_extra = _money(seven_preview["extra_amount"])
                    regular_extra = _money(regular_preview["extra_amount"])

                    seven_advance_dates: tuple[date, ...] = ()
                    if (
                        body.extra_allocation_choice
                        is CombinedExtraAllocationChoice.SEVEN_BY_SEVEN_ADVANCE
                    ):
                        seven_advance_dates = _seven_by_seven_advance_dates(
                            connection,
                            loan_id=seven_leg.loan_id,
                            collection_date=body.collection_date,
                            amount=seven_extra,
                        )

                    posted_legs: list[dict[str, object]] = []
                    total = Decimal("0.00")
                    applied_total = Decimal("0.00")
                    unallocated_total = Decimal("0.00")

                    def post_component(
                        *,
                        component: str,
                        leg: CombinedPaymentLeg,
                        amount: Decimal,
                        device_offset: int,
                        entry_type: CollectionEntryType = CollectionEntryType.PAYMENT,
                        route_revision: str | None = None,
                        allocation_intent: PaymentAllocationIntent = (
                            PaymentAllocationIntent.SCHEDULED
                        ),
                        covered_dates: tuple[date, ...] | None = None,
                    ):
                        nonlocal applied_total, total, unallocated_total
                        child_key = uuid5(
                            idempotency_key,
                            f"{component}:{leg.loan_id}",
                        )
                        command = CollectionCommand(
                            idempotency_key=child_key,
                            route_entry_id=str(leg.route_entry_id),
                            client_id=str(body.client_id),
                            loan_id=str(leg.loan_id),
                            collection_date=body.collection_date,
                            entry_type=entry_type,
                            amount=amount,
                            advance_from=(
                                covered_dates[0]
                                if entry_type is CollectionEntryType.ADVANCE
                                and covered_dates
                                else None
                            ),
                            advance_until=(
                                covered_dates[-1]
                                if entry_type is CollectionEntryType.ADVANCE
                                and covered_dates
                                else None
                            ),
                            covered_dates=(
                                covered_dates
                                if covered_dates is not None
                                else (body.collection_date,)
                            ),
                            recorded_at=body.recorded_at,
                            device_id=body.device_id,
                            device_sequence=body.device_sequence + device_offset,
                            note=("Atomic Regular + 7x7 one-total Pay • " + component),
                            route_revision=(
                                route_revision or leg.route_revision.strip()
                            ),
                            payment_allocation_intent=allocation_intent,
                            past_due_followup=(
                                body.regular_past_due_followup.to_input()
                                if component.startswith("regular_")
                                and preview["regular_past_due_followup_required"]
                                and body.regular_past_due_followup is not None
                                else None
                            ),
                        )
                        posted = bridge.post_collection(connection, actor, command)
                        with connection.cursor(row_factory=dict_row) as cursor:
                            cursor.execute(
                                """
                                select amount, applied_amount, unallocated_amount,
                                       allocation_state
                                from lending.collection_transactions
                                where id = %s
                                """,
                                (UUID(posted.server_transaction_id),),
                            )
                            receipt = cursor.fetchone()
                        if receipt is None:
                            raise CollectionRejected(
                                "The saved combined receipt evidence could not be reloaded.",
                                code="combined_receipt_evidence_missing",
                            )
                        cash_received = _money(receipt["amount"])
                        applied = _money(receipt["applied_amount"])
                        unallocated = _money(receipt["unallocated_amount"])
                        total += cash_received
                        applied_total += applied
                        unallocated_total += unallocated
                        leg_result: dict[str, object] = {
                            "loan_id": str(leg.loan_id),
                            "transaction_id": posted.server_transaction_id,
                            "receipt_number": posted.receipt_number,
                            "amount": format(cash_received, "f"),
                            "applied_amount": format(applied, "f"),
                            "unallocated_amount": format(unallocated, "f"),
                            "allocation_state": str(receipt["allocation_state"]),
                            "allocation_component": component,
                            "official_balance": format(posted.official_balance, "f"),
                            "route_revision": posted.route_revision,
                            "message": posted.message,
                        }
                        if posted.result_metadata:
                            leg_result["result"] = dict(posted.result_metadata)
                        posted_legs.append(leg_result)
                        return posted

                    device_offset = 0
                    seven_revision = seven_leg.route_revision.strip()
                    if seven_scheduled > ZERO:
                        posted = post_component(
                            component="seven_by_seven_scheduled",
                            leg=seven_leg,
                            amount=seven_scheduled,
                            device_offset=device_offset,
                        )
                        device_offset += 1
                        seven_revision = posted.route_revision or seven_revision

                    if regular_scheduled > ZERO or regular_extra > ZERO:
                        regular_intent = PaymentAllocationIntent.SCHEDULED
                        if (
                            body.extra_allocation_choice
                            is CombinedExtraAllocationChoice.REGULAR_ADVANCE
                        ):
                            regular_intent = PaymentAllocationIntent.EXTRA_AS_ADVANCE
                        elif (
                            body.extra_allocation_choice
                            is CombinedExtraAllocationChoice.REGULAR_PRINCIPAL_REDUCTION
                        ):
                            regular_intent = (
                                PaymentAllocationIntent.EXTRA_AS_PRINCIPAL_REDUCTION
                            )
                        post_component(
                            component=(
                                "regular_scheduled_and_extra"
                                if regular_extra > ZERO
                                else "regular_scheduled"
                            ),
                            leg=regular_leg,
                            amount=_money(regular_scheduled + regular_extra),
                            device_offset=device_offset,
                            allocation_intent=regular_intent,
                        )
                        device_offset += 1

                    if seven_extra > ZERO:
                        if (
                            body.extra_allocation_choice
                            is CombinedExtraAllocationChoice.SEVEN_BY_SEVEN_ADVANCE
                        ):
                            post_component(
                                component="seven_by_seven_advance",
                                leg=seven_leg,
                                amount=seven_extra,
                                device_offset=device_offset,
                                entry_type=CollectionEntryType.ADVANCE,
                                route_revision=seven_revision,
                                covered_dates=seven_advance_dates,
                            )
                        elif (
                            body.extra_allocation_choice
                            is CombinedExtraAllocationChoice.SEVEN_BY_SEVEN_EXTRA_PRINCIPAL
                        ):
                            post_component(
                                component="seven_by_seven_extra_principal",
                                leg=seven_leg,
                                amount=seven_extra,
                                device_offset=device_offset,
                                route_revision=seven_revision,
                                allocation_intent=(
                                    PaymentAllocationIntent.EXTRA_AS_PRINCIPAL_REDUCTION
                                ),
                                covered_dates=(),
                            )
                        device_offset += 1

                    expected_cash = _money(body.cash_received_amount)
                    planned_cash = _money(
                        seven_scheduled
                        + regular_scheduled
                        + regular_extra
                        + seven_extra
                    )
                    if (
                        planned_cash != expected_cash
                        or total != expected_cash
                        or applied_total != total
                        or unallocated_total != ZERO
                    ):
                        raise CollectionRejected(
                            "The protected combined allocation changed while saving. "
                            "Nothing was recorded; refresh the route and try again.",
                            code="combined_cash_allocation_contradiction",
                        )

                    result_payload: dict[str, object] = {
                        "status": "accepted",
                        "duplicate": False,
                        "client_transaction_id": str(idempotency_key),
                        "client_id": str(body.client_id),
                        "total_amount": format(total.quantize(Decimal("0.01")), "f"),
                        "applied_total_amount": format(_money(applied_total), "f"),
                        "unallocated_total_amount": format(
                            _money(unallocated_total), "f"
                        ),
                        "cash_allocation_state": (
                            "fully_allocated"
                        ),
                        "allocation_status": preview["status"],
                        "allocation_hash": preview["allocation_hash"],
                        "extra_allocation_choice": preview["extra_allocation_choice"],
                        "legs": posted_legs,
                        "message": (
                            "One cash total was allocated and saved atomically "
                            "across Regular + 7x7."
                        ),
                    }
                    with connection.cursor() as cursor:
                        cursor.execute(
                            """
                            insert into mobile.gilbic_combined_collection_idempotency (
                                idempotency_key,
                                collector_account_id,
                                registered_device_id,
                                canonical_request_hash,
                                request_payload,
                                result_payload
                            ) values (%s, %s, %s, %s, %s, %s)
                            """,
                            (
                                idempotency_key,
                                UUID(actor.account_id),
                                UUID(actor.storage_device_id),
                                request_hash,
                                Jsonb(
                                    {
                                        k: v
                                        for k, v in canonical.items()
                                        if k != "device_id"
                                    }
                                ),
                                Jsonb(result_payload),
                            ),
                        )
                    return {"success": True, "data": result_payload}
        except CollectionConflict as error:
            raise HTTPException(
                status_code=409,
                detail={"code": error.code, "message": error.message},
            ) from error
        except CollectionRejected as error:
            raise HTTPException(
                status_code=422,
                detail={"code": error.code, "message": error.message},
            ) from error

    return router
