from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from gilbic_backend.collection_void_repository import CollectionVoidRecord
from gilbic_backend.seven_by_seven_extra_principal_reversal import (
    ExtraPrincipalReversalIdempotencyMismatch,
    ExtraPrincipalReversalIdempotencyRequired,
    ExtraPrincipalReversalRequest,
    begin_extra_principal_reversal_request,
    store_completed_reversal_request,
)

KEY = UUID("11111111-1111-4111-8111-111111111111")
ACTOR_ID = UUID("22222222-2222-4222-8222-222222222222")
TRANSACTION_ID = UUID("33333333-3333-4333-8333-333333333333")
ADJUSTMENT_ID = UUID("44444444-4444-4444-8444-444444444444")
REQUEST_ID = UUID("55555555-5555-4555-8555-555555555555")
CLIENT_ID = UUID("66666666-6666-4666-8666-666666666666")
LOAN_ID = UUID("77777777-7777-4777-8777-777777777777")
COLLECTOR_ID = UUID("88888888-8888-4888-8888-888888888888")


class FakeCursor:
    def __init__(self, existing: dict[str, object] | None) -> None:
        self.existing = existing

    def execute(self, query, params):
        del params
        if "seven_by_seven_extra_principal_reversal_requests" in query:
            self._next = self.existing
        else:
            self._next = None
        return self

    def fetchone(self):
        return self._next


class RecordingCursor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object | None]] = []

    def execute(self, query, params=None):
        self.calls.append((query, params))
        return self


def _request(*, reason: str) -> ExtraPrincipalReversalRequest:
    return ExtraPrincipalReversalRequest.canonical(
        idempotency_key=KEY,
        actor_user_id=ACTOR_ID,
        transaction_id=TRANSACTION_ID,
        adjustment_id=ADJUSTMENT_ID,
        reason=reason,
    )


def test_extra_principal_reversal_requires_idempotency_key() -> None:
    with pytest.raises(ExtraPrincipalReversalIdempotencyRequired):
        ExtraPrincipalReversalRequest.canonical(
            idempotency_key=None,
            actor_user_id=ACTOR_ID,
            transaction_id=TRANSACTION_ID,
            adjustment_id=ADJUSTMENT_ID,
            reason="Wrong receipt",
        )


def test_changed_reversal_retry_conflicts() -> None:
    original = _request(reason="Wrong receipt")
    cursor = FakeCursor(
        {
            "canonical_request_hash": original.canonical_request_hash,
            "result_payload": {},
        }
    )

    with pytest.raises(ExtraPrincipalReversalIdempotencyMismatch):
        begin_extra_principal_reversal_request(
            cursor,
            idempotency_key=KEY,
            actor_user_id=ACTOR_ID,
            transaction_id=TRANSACTION_ID,
            adjustment_id=ADJUSTMENT_ID,
            reason="Different reason",
        )


def test_exact_completed_retry_reloads_immutable_void_result() -> None:
    original = _request(reason="Wrong receipt")
    payload = {
        "request_id": str(REQUEST_ID),
        "adjustment_id": str(ADJUSTMENT_ID),
        "transaction_id": str(TRANSACTION_ID),
        "outcome": "completed",
        "released_refund_amount": "0.00",
        "collection_void": {
            "transaction_id": str(TRANSACTION_ID),
            "receipt_number": "GBC-20990101-00000001",
            "client_id": str(CLIENT_ID),
            "client_code": "CLIENT-001",
            "client_name": "Test Client",
            "loan_id": str(LOAN_ID),
            "collector_user_id": str(COLLECTOR_ID),
            "collector_name": "Test Collector",
            "collection_date": date(2099, 1, 1).isoformat(),
            "entry_type": "payment",
            "amount": "100.00",
            "covered_dates": [],
            "restored_balance": "3000.00",
            "state_version": 2,
            "reason": "Wrong receipt",
            "voided_at": datetime(2099, 1, 1, 9, tzinfo=UTC).isoformat(),
        },
    }
    cursor = FakeCursor(
        {
            "canonical_request_hash": original.canonical_request_hash,
            "result_payload": payload,
        }
    )

    _, result = begin_extra_principal_reversal_request(
        cursor,
        idempotency_key=KEY,
        actor_user_id=ACTOR_ID,
        transaction_id=TRANSACTION_ID,
        adjustment_id=ADJUSTMENT_ID,
        reason="Wrong receipt",
    )

    assert result is not None
    assert result.outcome == "completed"
    assert result.released_refund_amount == Decimal("0.00")
    assert result.collection_void is not None
    assert result.collection_void.restored_balance == Decimal("3000.00")


def test_completed_request_links_the_collection_void_evidence() -> None:
    cursor = RecordingCursor()
    collection_void_id = UUID("99999999-9999-4999-8999-999999999999")
    record = CollectionVoidRecord(
        transaction_id=TRANSACTION_ID,
        receipt_number="GBC-20990101-00000001",
        client_id=CLIENT_ID,
        client_code="CLIENT-001",
        client_name="Test Client",
        loan_id=LOAN_ID,
        collector_user_id=COLLECTOR_ID,
        collector_name="Test Collector",
        collection_date=date(2099, 1, 1),
        entry_type="payment",
        amount=Decimal("100.00"),
        covered_dates=(),
        restored_balance=Decimal("3000.00"),
        state_version=2,
        reason="Wrong receipt",
        voided_at=datetime(2099, 1, 1, 9, tzinfo=UTC),
    )

    result = store_completed_reversal_request(
        cursor,
        request=_request(reason="Wrong receipt"),
        collection_void_id=collection_void_id,
        collection_void=record,
    )

    insert_params = cursor.calls[-1][1]
    assert insert_params is not None
    assert insert_params[8] == collection_void_id
    assert result.collection_void == record
