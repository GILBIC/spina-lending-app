from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from hashlib import sha256
from typing import Any
from uuid import UUID

from .seven_by_seven_extra_principal import (
    FutureInstallmentPrincipalState,
    SevenBySevenExtraPrincipalError,
    normalize_future_installment_principal_state,
    plan_seven_by_seven_extra_principal_tail,
)
from .seven_by_seven_operational_allocator import ZERO, money


class SevenBySevenExtraPrincipalReplayError(ValueError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class ActiveExtraPrincipalEvent:
    adjustment_id: UUID
    transaction_id: UUID
    principal_reduction: Decimal
    resulting_operational_version: int
    collection_date: date | None = None


@dataclass(frozen=True, slots=True)
class ReplayedExtraPrincipalInstallment:
    installment_id: int
    installment_number: int
    effective_due_date: date
    signed_amount: Decimal
    signed_principal: Decimal
    signed_interest: Decimal
    operational_amount: Decimal
    operational_principal: Decimal
    operational_interest: Decimal
    removed: bool
    last_active_adjustment_id: UUID | None


@dataclass(frozen=True, slots=True)
class ExtraPrincipalReplayResult:
    operational_rows: tuple[ReplayedExtraPrincipalInstallment, ...]
    active_adjustment_ids: tuple[UUID, ...]
    future_principal: Decimal
    source_history_digest: str
    operational_state_digest: str


def require_extra_principal_interest_clear(
    *,
    past_due_interest: Decimal,
    today_interest: Decimal,
) -> None:
    if money(past_due_interest) != ZERO or money(today_interest) != ZERO:
        raise SevenBySevenExtraPrincipalReplayError(
            "Past Due Interest and Today Interest must be fully paid before "
            "7x7 Extra Principal.",
            code="seven_by_seven_extra_principal_interest_outstanding",
        )


def replay_extra_principal_history(
    *,
    signed_installments: Iterable[FutureInstallmentPrincipalState],
    active_events: Iterable[ActiveExtraPrincipalEvent],
) -> ExtraPrincipalReplayResult:
    try:
        signed_rows = tuple(
            sorted(
                (
                    normalize_future_installment_principal_state(row)
                    for row in signed_installments
                ),
                key=lambda row: (
                    row.effective_due_date,
                    row.installment_number,
                    row.installment_id,
                ),
            )
        )
    except SevenBySevenExtraPrincipalError as error:
        raise _replay_conflict(str(error)) from error

    if not signed_rows:
        raise _replay_conflict(
            "The immutable signed 7x7 schedule has no installments to replay."
        )
    if len({row.installment_id for row in signed_rows}) != len(signed_rows):
        raise _replay_conflict(
            "The immutable signed 7x7 schedule contains duplicate installment "
            "identities."
        )

    events = tuple(
        sorted(
            (
                ActiveExtraPrincipalEvent(
                    adjustment_id=event.adjustment_id,
                    transaction_id=event.transaction_id,
                    principal_reduction=money(event.principal_reduction),
                    resulting_operational_version=event.resulting_operational_version,
                    collection_date=event.collection_date,
                )
                for event in active_events
            ),
            key=lambda event: (
                event.resulting_operational_version,
                str(event.adjustment_id),
            ),
        )
    )
    _validate_events(events)

    current_rows = signed_rows
    final_by_id = {
        row.installment_id: ReplayedExtraPrincipalInstallment(
            installment_id=row.installment_id,
            installment_number=row.installment_number,
            effective_due_date=row.effective_due_date,
            signed_amount=money(
                row.signed_contractual_amount or row.contractual_amount
            ),
            signed_principal=money(
                row.signed_principal_component or row.principal_component
            ),
            signed_interest=money(
                row.signed_interest_component
                if row.signed_interest_component is not None
                else row.interest_component
            ),
            operational_amount=money(row.contractual_amount),
            operational_principal=money(row.principal_component),
            operational_interest=money(row.interest_component),
            removed=False,
            last_active_adjustment_id=None,
        )
        for row in signed_rows
    }

    for event in events:
        eligible_rows = tuple(
            row
            for row in current_rows
            if event.collection_date is None
            or row.effective_due_date > event.collection_date
        )
        if not eligible_rows:
            raise _replay_conflict(
                "An active Extra Principal event has no eligible future signed tail."
            )
        try:
            plan = plan_seven_by_seven_extra_principal_tail(
                principal_reduction=event.principal_reduction,
                future_installments=eligible_rows,
            )
        except SevenBySevenExtraPrincipalError as error:
            raise _replay_conflict(
                "Active Extra Principal history cannot be replayed safely against "
                f"the signed 7x7 schedule: {error}"
            ) from error

        projection_by_id = {
            projection.installment_id: projection for projection in plan.installments
        }
        next_rows: list[FutureInstallmentPrincipalState] = []
        for current in current_rows:
            projection = projection_by_id.get(current.installment_id)
            if projection is None:
                next_rows.append(current)
                continue
            final_by_id[projection.installment_id] = ReplayedExtraPrincipalInstallment(
                installment_id=projection.installment_id,
                installment_number=projection.installment_number,
                effective_due_date=projection.effective_due_date,
                signed_amount=projection.signed_contractual_amount,
                signed_principal=projection.signed_principal_component,
                signed_interest=projection.signed_interest_component,
                operational_amount=projection.operational_amount,
                operational_principal=(projection.operational_principal_component),
                operational_interest=(
                    ZERO
                    if projection.removed_from_operational_schedule
                    else projection.signed_interest_component
                ),
                removed=projection.removed_from_operational_schedule,
                last_active_adjustment_id=event.adjustment_id,
            )
            if projection.removed_from_operational_schedule:
                continue
            next_rows.append(
                FutureInstallmentPrincipalState(
                    installment_id=projection.installment_id,
                    installment_number=projection.installment_number,
                    effective_due_date=projection.effective_due_date,
                    contractual_amount=projection.operational_amount,
                    principal_component=(projection.operational_principal_component),
                    interest_component=projection.signed_interest_component,
                    advance_allocated=ZERO,
                    signed_contractual_amount=(projection.signed_contractual_amount),
                    signed_principal_component=(projection.signed_principal_component),
                    signed_interest_component=projection.signed_interest_component,
                )
            )
        current_rows = tuple(next_rows)

    operational_rows = tuple(final_by_id[row.installment_id] for row in signed_rows)
    future_principal = money(
        sum((row.operational_principal for row in operational_rows), ZERO)
    )
    source_payload = {
        "events": [
            {
                "adjustment_id": str(event.adjustment_id),
                "collection_date": (
                    event.collection_date.isoformat()
                    if event.collection_date is not None
                    else None
                ),
                "principal_reduction": _money_text(event.principal_reduction),
                "resulting_operational_version": (event.resulting_operational_version),
                "transaction_id": str(event.transaction_id),
            }
            for event in events
        ],
        "signed_installments": [
            {
                "effective_due_date": row.effective_due_date.isoformat(),
                "installment_id": row.installment_id,
                "installment_number": row.installment_number,
                "signed_amount": _money_text(
                    row.signed_contractual_amount or row.contractual_amount
                ),
                "signed_interest": _money_text(
                    row.signed_interest_component
                    if row.signed_interest_component is not None
                    else row.interest_component
                ),
                "signed_principal": _money_text(
                    row.signed_principal_component or row.principal_component
                ),
            }
            for row in signed_rows
        ],
    }
    operational_payload = {
        "active_adjustment_ids": [str(event.adjustment_id) for event in events],
        "installments": [
            {
                "effective_due_date": row.effective_due_date.isoformat(),
                "installment_id": row.installment_id,
                "installment_number": row.installment_number,
                "last_active_adjustment_id": (
                    str(row.last_active_adjustment_id)
                    if row.last_active_adjustment_id is not None
                    else None
                ),
                "operational_amount": _money_text(row.operational_amount),
                "operational_interest": _money_text(row.operational_interest),
                "operational_principal": _money_text(row.operational_principal),
                "removed": row.removed,
                "signed_amount": _money_text(row.signed_amount),
                "signed_interest": _money_text(row.signed_interest),
                "signed_principal": _money_text(row.signed_principal),
            }
            for row in operational_rows
        ],
    }
    return ExtraPrincipalReplayResult(
        operational_rows=operational_rows,
        active_adjustment_ids=tuple(event.adjustment_id for event in events),
        future_principal=future_principal,
        source_history_digest=_digest(source_payload),
        operational_state_digest=_digest(operational_payload),
    )


def replay_extra_principal_from_database(
    cursor: Any,
    *,
    schedule_id: UUID,
    excluded_adjustment_id: UUID | None = None,
) -> ExtraPrincipalReplayResult:
    """Rebuild one operational schedule from immutable database evidence."""

    cursor.execute(
        """
        select
            installment.id,
            installment.installment_number,
            installment.effective_due_date,
            installment.contractual_amount,
            installment.principal_component,
            installment.interest_component
        from lending.loan_contract_installments_operational installment
        where installment.schedule_id = %s
        order by
            installment.effective_due_date,
            installment.installment_number,
            installment.id
        """,
        (schedule_id,),
    )
    signed_installments = tuple(
        FutureInstallmentPrincipalState(
            installment_id=int(row["id"]),
            installment_number=int(row["installment_number"]),
            effective_due_date=row["effective_due_date"],
            contractual_amount=money(row["contractual_amount"]),
            principal_component=money(row["principal_component"]),
            interest_component=money(row["interest_component"]),
            signed_contractual_amount=money(row["contractual_amount"]),
            signed_principal_component=money(row["principal_component"]),
            signed_interest_component=money(row["interest_component"]),
        )
        for row in cursor.fetchall()
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
          and (%s::uuid is null or adjustment.id <> %s::uuid)
        order by adjustment.resulting_operational_version, adjustment.id
        """,
        (schedule_id, excluded_adjustment_id, excluded_adjustment_id),
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
    return replay_extra_principal_history(
        signed_installments=signed_installments,
        active_events=active_events,
    )


def verify_persisted_extra_principal_replay(
    cursor: Any,
    *,
    schedule_id: UUID,
    expected_source_history_digest: str | None = None,
    expected_operational_state_digest: str | None = None,
) -> ExtraPrincipalReplayResult:
    """Independently prove the persisted overlay equals immutable replay."""

    replayed = replay_extra_principal_from_database(
        cursor,
        schedule_id=schedule_id,
    )
    if (
        expected_source_history_digest is not None
        and replayed.source_history_digest != expected_source_history_digest
    ):
        raise _replay_conflict(
            "The reconstructed Extra Principal source-history digest does not match "
            "the immutable reversal evidence."
        )
    if (
        expected_operational_state_digest is not None
        and replayed.operational_state_digest != expected_operational_state_digest
    ):
        raise _replay_conflict(
            "The reconstructed Extra Principal operational-state digest does not "
            "match the immutable reversal evidence."
        )

    cursor.execute(
        """
        select
            installment.id,
            installment.operational_amount,
            installment.operational_principal_component,
            installment.operational_interest_component,
            installment.removed_from_operational_schedule,
            installment.last_extra_principal_adjustment_id
        from lending.loan_contract_installments_operational installment
        where installment.schedule_id = %s
        order by
            installment.effective_due_date,
            installment.installment_number,
            installment.id
        """,
        (schedule_id,),
    )
    actual_by_id = {int(row["id"]): row for row in cursor.fetchall()}
    if set(actual_by_id) != {
        row.installment_id for row in replayed.operational_rows
    }:
        raise _replay_conflict(
            "The persisted operational schedule does not contain the exact signed "
            "installment identities."
        )
    for row in replayed.operational_rows:
        actual = actual_by_id[row.installment_id]
        if (
            money(actual["operational_amount"]) != row.operational_amount
            or money(actual["operational_principal_component"])
            != row.operational_principal
            or money(actual["operational_interest_component"])
            != row.operational_interest
            or bool(actual["removed_from_operational_schedule"]) != row.removed
            or actual["last_extra_principal_adjustment_id"]
            != row.last_active_adjustment_id
        ):
            raise _replay_conflict(
                "The persisted operational schedule does not match immutable Extra "
                "Principal history."
            )
    return replayed


def _validate_events(events: tuple[ActiveExtraPrincipalEvent, ...]) -> None:
    if len({event.adjustment_id for event in events}) != len(events):
        raise _replay_conflict(
            "Active Extra Principal history contains a duplicate adjustment identity."
        )
    if len({event.transaction_id for event in events}) != len(events):
        raise _replay_conflict(
            "Active Extra Principal history contains a duplicate transaction identity."
        )
    if len({event.resulting_operational_version for event in events}) != len(events):
        raise _replay_conflict(
            "Active Extra Principal history contains a duplicate operational version."
        )
    if any(
        event.resulting_operational_version <= 0 or event.principal_reduction <= ZERO
        for event in events
    ):
        raise _replay_conflict(
            "Active Extra Principal history contains an invalid version or reduction."
        )
    dated_events = tuple(
        event.collection_date for event in events if event.collection_date is not None
    )
    if dated_events != tuple(sorted(dated_events)):
        raise _replay_conflict(
            "Active Extra Principal history contains non-chronological receipt dates."
        )


def _digest(payload: Mapping[str, object]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def _money_text(value: Decimal) -> str:
    return format(money(value), ".2f")


def _replay_conflict(message: str) -> SevenBySevenExtraPrincipalReplayError:
    return SevenBySevenExtraPrincipalReplayError(
        message,
        code="seven_by_seven_extra_principal_replay_conflict",
    )
