from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal, cast
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from .collection_void_repository import (
    CollectionVoidConflict,
    CollectionVoidInvalid,
    CollectionVoidRecord,
)
from .seven_by_seven_extra_principal_replay import (
    SevenBySevenExtraPrincipalReplayError,
    verify_persisted_extra_principal_replay,
)

ZERO = Decimal("0.00")


class ExtraPrincipalReversalIdempotencyRequired(CollectionVoidInvalid):
    code = "seven_by_seven_extra_principal_reversal_idempotency_required"


class ExtraPrincipalReversalIdempotencyMismatch(CollectionVoidConflict):
    code = "seven_by_seven_extra_principal_reversal_idempotency_mismatch"


@dataclass(frozen=True, slots=True)
class ExtraPrincipalReversalRequest:
    idempotency_key: UUID
    actor_user_id: UUID
    transaction_id: UUID
    adjustment_id: UUID
    reason: str
    canonical_request_hash: str

    @classmethod
    def canonical(
        cls,
        *,
        idempotency_key: UUID | None,
        actor_user_id: UUID,
        transaction_id: UUID,
        adjustment_id: UUID,
        reason: str,
    ) -> ExtraPrincipalReversalRequest:
        if idempotency_key is None:
            raise ExtraPrincipalReversalIdempotencyRequired(
                "An idempotency key is required to reverse a 7x7 Extra Principal "
                "receipt."
            )
        payload = {
            "actor_user_id": str(actor_user_id),
            "adjustment_id": str(adjustment_id),
            "idempotency_key": str(idempotency_key),
            "reason": reason,
            "transaction_id": str(transaction_id),
        }
        return cls(
            idempotency_key=idempotency_key,
            actor_user_id=actor_user_id,
            transaction_id=transaction_id,
            adjustment_id=adjustment_id,
            reason=reason,
            canonical_request_hash=_canonical_hash(payload),
        )


@dataclass(frozen=True, slots=True)
class ExtraPrincipalReversalRequestResult:
    request_id: UUID
    adjustment_id: UUID
    transaction_id: UUID
    outcome: Literal["completed", "blocked_refund_released"]
    released_refund_amount: Decimal
    result_payload: dict[str, object]
    collection_void: CollectionVoidRecord | None


def begin_extra_principal_reversal_request(
    cursor: Any,
    *,
    idempotency_key: UUID | None,
    actor_user_id: UUID,
    transaction_id: UUID,
    adjustment_id: UUID,
    reason: str,
) -> tuple[ExtraPrincipalReversalRequest, ExtraPrincipalReversalRequestResult | None]:
    request = ExtraPrincipalReversalRequest.canonical(
        idempotency_key=idempotency_key,
        actor_user_id=actor_user_id,
        transaction_id=transaction_id,
        adjustment_id=adjustment_id,
        reason=reason,
    )
    cursor.execute(
        "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
        (f"gilbic-extra-principal-reversal:{request.idempotency_key}",),
    )
    cursor.execute(
        "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
        (f"gilbic-management-collection-void:{transaction_id}",),
    )
    existing = cursor.execute(
        """
        select canonical_request_hash, result_payload
        from lending.seven_by_seven_extra_principal_reversal_requests
        where idempotency_key = %s
        for update
        """,
        (request.idempotency_key,),
    ).fetchone()
    if existing is None:
        return request, None
    if existing["canonical_request_hash"] != request.canonical_request_hash:
        raise ExtraPrincipalReversalIdempotencyMismatch(
            "This Extra Principal reversal key was already used for different data."
        )
    return request, _result_from_payload(existing["result_payload"])


def lock_released_refund_amount(cursor: Any, *, adjustment_id: UUID) -> Decimal:
    rows = cursor.execute(
        """
        select release.released_amount
        from lending.loan_unused_advance_refund_due_releases release
        join lending.loan_unused_advance_refund_due_approvals approval
          on approval.id = release.approval_id
        where approval.adjustment_id = %s
        order by release.id
        for update of release
        """,
        (adjustment_id,),
    ).fetchall()
    return sum((Decimal(row["released_amount"]) for row in rows), start=ZERO)


def store_blocked_reversal_request(
    cursor: Any,
    *,
    request: ExtraPrincipalReversalRequest,
    released_refund_amount: Decimal,
) -> ExtraPrincipalReversalRequestResult:
    request_id = uuid4()
    message = (
        "Physical Refund Due cash was already released. Automatic reversal is blocked; "
        "Management must use a later reviewed correction."
    )
    payload: dict[str, object] = {
        "request_id": str(request_id),
        "adjustment_id": str(request.adjustment_id),
        "transaction_id": str(request.transaction_id),
        "outcome": "blocked_refund_released",
        "released_refund_amount": _money_text(released_refund_amount),
        "code": "seven_by_seven_extra_principal_reversal_refund_released",
        "message": message,
    }
    _insert_request(
        cursor,
        request_id=request_id,
        request=request,
        outcome="blocked_refund_released",
        released_refund_amount=released_refund_amount,
        result_payload=payload,
    )
    return ExtraPrincipalReversalRequestResult(
        request_id=request_id,
        adjustment_id=request.adjustment_id,
        transaction_id=request.transaction_id,
        outcome="blocked_refund_released",
        released_refund_amount=released_refund_amount,
        result_payload=payload,
        collection_void=None,
    )


def store_completed_reversal_request(
    cursor: Any,
    *,
    request: ExtraPrincipalReversalRequest,
    collection_void_id: UUID,
    collection_void: CollectionVoidRecord,
) -> ExtraPrincipalReversalRequestResult:
    request_id = uuid4()
    payload: dict[str, object] = {
        "request_id": str(request_id),
        "adjustment_id": str(request.adjustment_id),
        "transaction_id": str(request.transaction_id),
        "outcome": "completed",
        "released_refund_amount": "0.00",
        "collection_void": _collection_void_payload(collection_void),
    }
    _insert_request(
        cursor,
        request_id=request_id,
        request=request,
        outcome="completed",
        collection_void_id=collection_void_id,
        released_refund_amount=ZERO,
        result_payload=payload,
    )
    return ExtraPrincipalReversalRequestResult(
        request_id=request_id,
        adjustment_id=request.adjustment_id,
        transaction_id=request.transaction_id,
        outcome="completed",
        released_refund_amount=ZERO,
        result_payload=payload,
        collection_void=collection_void,
    )


def verify_completed_extra_principal_reversal(
    cursor: Any,
    *,
    adjustment_id: UUID,
) -> None:
    row = cursor.execute(
        """
        select
            reversal.schedule_id,
            reversal.source_history_digest,
            reversal.operational_state_digest
        from lending.seven_by_seven_extra_principal_reversals reversal
        where reversal.adjustment_id = %s
        """,
        (adjustment_id,),
    ).fetchone()
    if row is None:
        raise CollectionVoidConflict(
            "The Extra Principal void did not create immutable operational "
            "reversal evidence."
        )
    try:
        verify_persisted_extra_principal_replay(
            cursor,
            schedule_id=row["schedule_id"],
            expected_source_history_digest=row["source_history_digest"],
            expected_operational_state_digest=row["operational_state_digest"],
        )
    except SevenBySevenExtraPrincipalReplayError as error:
        raise CollectionVoidConflict(str(error)) from error


def _insert_request(
    cursor: Any,
    *,
    request_id: UUID,
    request: ExtraPrincipalReversalRequest,
    outcome: Literal["completed", "blocked_refund_released"],
    collection_void_id: UUID | None = None,
    released_refund_amount: Decimal,
    result_payload: dict[str, object],
) -> None:
    cursor.execute(
        "select set_config('spina.extra_principal_reversal_write', 'on', true)"
    )
    cursor.execute(
        """
        insert into lending.seven_by_seven_extra_principal_reversal_requests (
            id, idempotency_key, canonical_request_hash, transaction_id,
            adjustment_id, requested_by_user_id, reason, outcome,
            collection_void_id, released_refund_amount, result_payload
        ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            request_id,
            request.idempotency_key,
            request.canonical_request_hash,
            request.transaction_id,
            request.adjustment_id,
            request.actor_user_id,
            request.reason,
            outcome,
            collection_void_id,
            released_refund_amount,
            Jsonb(result_payload),
        ),
    )


def _collection_void_payload(record: CollectionVoidRecord) -> dict[str, object]:
    return {
        "transaction_id": str(record.transaction_id),
        "receipt_number": record.receipt_number,
        "client_id": str(record.client_id),
        "client_code": record.client_code,
        "client_name": record.client_name,
        "loan_id": str(record.loan_id),
        "collector_user_id": str(record.collector_user_id),
        "collector_name": record.collector_name,
        "collection_date": record.collection_date.isoformat(),
        "entry_type": record.entry_type,
        "amount": _money_text(record.amount),
        "covered_dates": [value.isoformat() for value in record.covered_dates],
        "restored_balance": _money_text(record.restored_balance),
        "state_version": record.state_version,
        "reason": record.reason,
        "voided_at": record.voided_at.isoformat(),
    }


def _result_from_payload(payload: Any) -> ExtraPrincipalReversalRequestResult:
    value = dict(payload or {})
    try:
        outcome = str(value["outcome"])
        if outcome not in {"completed", "blocked_refund_released"}:
            raise ValueError("invalid outcome")
        typed_outcome = cast(
            Literal["completed", "blocked_refund_released"],
            outcome,
        )
        collection_payload = value.get("collection_void")
        collection_void = (
            _collection_void_from_payload(collection_payload)
            if collection_payload is not None
            else None
        )
        return ExtraPrincipalReversalRequestResult(
            request_id=UUID(value["request_id"]),
            adjustment_id=UUID(value["adjustment_id"]),
            transaction_id=UUID(value["transaction_id"]),
            outcome=typed_outcome,
            released_refund_amount=Decimal(value["released_refund_amount"]),
            result_payload=value,
            collection_void=collection_void,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise CollectionVoidConflict(
            "Stored Extra Principal reversal request evidence is invalid."
        ) from error


def _collection_void_from_payload(payload: Any) -> CollectionVoidRecord:
    from datetime import date, datetime

    value = dict(payload or {})
    return CollectionVoidRecord(
        transaction_id=UUID(value["transaction_id"]),
        receipt_number=str(value["receipt_number"]),
        client_id=UUID(value["client_id"]),
        client_code=str(value["client_code"]),
        client_name=str(value["client_name"]),
        loan_id=UUID(value["loan_id"]),
        collector_user_id=UUID(value["collector_user_id"]),
        collector_name=str(value["collector_name"]),
        collection_date=date.fromisoformat(value["collection_date"]),
        entry_type=str(value["entry_type"]),
        amount=Decimal(value["amount"]),
        covered_dates=tuple(
            date.fromisoformat(item) for item in value["covered_dates"]
        ),
        restored_balance=Decimal(value["restored_balance"]),
        state_version=int(value["state_version"]),
        reason=str(value["reason"]),
        voided_at=datetime.fromisoformat(value["voided_at"]),
    )


def _canonical_hash(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _money_text(value: Decimal) -> str:
    return format(Decimal(value).quantize(Decimal("0.01")), "f")
