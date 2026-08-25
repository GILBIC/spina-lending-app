from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest

from spina_mobile_collections.contracts import (
    ActorContext,
    CollectionCommand,
    CollectionEntryType,
    CollectionOutcome,
    CollectionStatus,
    PastDueFollowupInput,
    PastDueReasonCode,
    PostedCollection,
)
from spina_mobile_collections.service import (
    CONTRACT_VERSION,
    CollectionProtocolError,
    CollectionSubmissionService,
    SubmissionHeaders,
)

KEY = UUID("6cb93829-dccd-4d43-a25c-a1f31859cc1b")


class ThreadSafeExecutor:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: dict[UUID, tuple[str, PostedCollection]] = {}
        self.post_count = 0

    def execute(
        self,
        *,
        actor: ActorContext,
        command: CollectionCommand,
        canonical_payload: dict[str, Any],
        request_hash: str,
    ) -> CollectionOutcome:
        del actor, canonical_payload
        with self._lock:
            existing = self._records.get(command.idempotency_key)
            if existing is not None:
                stored_hash, posted = existing
                if stored_hash != request_hash:
                    return CollectionOutcome(
                        status=CollectionStatus.CONFLICT,
                        idempotency_key=command.idempotency_key,
                        message="Changed payload",
                        code="idempotency_mismatch",
                    )
                return CollectionOutcome(
                    status=CollectionStatus.DUPLICATE,
                    idempotency_key=command.idempotency_key,
                    message="Previously accepted",
                    posted=posted,
                )

            self.post_count += 1
            posted = PostedCollection(
                server_transaction_id=f"collection-{self.post_count}",
                receipt_number=f"OR-{self.post_count:08d}",
                official_balance=Decimal("4600.00"),
                accepted_at=datetime(2026, 7, 31, 5, 16, tzinfo=timezone.utc),
                route_revision="route-v4",
            )
            self._records[command.idempotency_key] = (request_hash, posted)
            return CollectionOutcome(
                status=CollectionStatus.ACCEPTED,
                idempotency_key=command.idempotency_key,
                message=posted.message,
                posted=posted,
            )


def actor() -> ActorContext:
    return ActorContext(
        account_id="collector-7",
        device_id="collector-phone-15",
        permissions=frozenset({"collection.create"}),
    )


def headers(key: UUID = KEY) -> SubmissionHeaders:
    return SubmissionHeaders(
        idempotency_key=key,
        client_transaction_id=key,
        device_id="collector-phone-15",
        contract_version=CONTRACT_VERSION,
    )


def command(*, amount: str = "200.00") -> CollectionCommand:
    return CollectionCommand(
        idempotency_key=KEY,
        route_entry_id="route-entry-304",
        client_id="client-304",
        loan_id="loan-815",
        collection_date=date(2026, 7, 31),
        entry_type=CollectionEntryType.PAYMENT,
        amount=Decimal(amount),
        recorded_at=datetime(2026, 7, 31, 5, 15, tzinfo=timezone.utc),
        device_id="collector-phone-15",
        device_sequence=45,
        note="Paid at home",
        route_revision="route-v3",
    )


def test_concurrent_retries_post_only_once() -> None:
    executor = ThreadSafeExecutor()
    service = CollectionSubmissionService(executor)

    def submit() -> CollectionOutcome:
        return service.submit(actor=actor(), headers=headers(), command=command())

    with ThreadPoolExecutor(max_workers=16) as pool:
        outcomes = list(pool.map(lambda _: submit(), range(32)))

    assert executor.post_count == 1
    assert sum(item.status is CollectionStatus.ACCEPTED for item in outcomes) == 1
    assert sum(item.status is CollectionStatus.DUPLICATE for item in outcomes) == 31
    assert {item.posted.receipt_number for item in outcomes if item.posted} == {
        "OR-00000001"
    }


def test_same_key_with_changed_payload_conflicts() -> None:
    executor = ThreadSafeExecutor()
    service = CollectionSubmissionService(executor)

    first = service.submit(actor=actor(), headers=headers(), command=command())
    changed = service.submit(
        actor=actor(),
        headers=headers(),
        command=command(amount="250.00"),
    )

    assert first.status is CollectionStatus.ACCEPTED
    assert changed.status is CollectionStatus.CONFLICT
    assert changed.code == "idempotency_mismatch"
    assert executor.post_count == 1


def test_decimal_and_utc_normalization_make_stable_replay() -> None:
    executor = ThreadSafeExecutor()
    service = CollectionSubmissionService(executor)

    first = service.submit(actor=actor(), headers=headers(), command=command(amount="200.00"))
    second = service.submit(actor=actor(), headers=headers(), command=command(amount="200.0"))

    assert first.status is CollectionStatus.ACCEPTED
    assert second.status is CollectionStatus.DUPLICATE


def test_rejects_mismatched_transaction_headers() -> None:
    service = CollectionSubmissionService(ThreadSafeExecutor())
    different = UUID("d35d95eb-7481-4f20-a2dd-f0cb13e3953e")

    with pytest.raises(CollectionProtocolError) as caught:
        service.submit(
            actor=actor(),
            headers=SubmissionHeaders(
                idempotency_key=KEY,
                client_transaction_id=different,
                device_id="collector-phone-15",
                contract_version=CONTRACT_VERSION,
            ),
            command=command(),
        )

    assert caught.value.code == "idempotency_key_mismatch"
    assert caught.value.status_code == 400


def test_rejects_unregistered_device() -> None:
    service = CollectionSubmissionService(ThreadSafeExecutor())

    with pytest.raises(CollectionProtocolError) as caught:
        service.submit(
            actor=actor(),
            headers=SubmissionHeaders(
                idempotency_key=KEY,
                client_transaction_id=KEY,
                device_id="other-phone",
                contract_version=CONTRACT_VERSION,
            ),
            command=command(),
        )

    assert caught.value.code == "device_not_registered"
    assert caught.value.status_code == 403


def test_validates_pass_shape() -> None:
    service = CollectionSubmissionService(ThreadSafeExecutor())
    invalid_pass = replace(
        command(),
        entry_type=CollectionEntryType.PASS,
        amount=Decimal("200"),
    )

    with pytest.raises(CollectionProtocolError) as caught:
        service.submit(actor=actor(), headers=headers(), command=invalid_pass)

    assert caught.value.code == "invalid_pass"


def test_unable_to_pay_requires_structured_past_due_reason() -> None:
    service = CollectionSubmissionService(ThreadSafeExecutor())
    missing_reason = replace(
        command(),
        entry_type=CollectionEntryType.PASS,
        amount=None,
        note="",
    )

    with pytest.raises(CollectionProtocolError) as caught:
        service.submit(actor=actor(), headers=headers(), command=missing_reason)

    assert caught.value.code == "past_due_reason_required"


def test_unable_to_pay_accepts_reason_separate_from_optional_note() -> None:
    executor = ThreadSafeExecutor()
    service = CollectionSubmissionService(executor)
    unable = replace(
        command(),
        entry_type=CollectionEntryType.PASS,
        amount=None,
        note="",
        past_due_followup=PastDueFollowupInput(
            reason_code=PastDueReasonCode.CLIENT_ABSENT,
            note="Neighbor said client returns tonight.",
        ),
    )

    result = service.submit(actor=actor(), headers=headers(), command=unable)

    assert result.status is CollectionStatus.ACCEPTED
    assert executor.post_count == 1


def test_promise_followup_is_part_of_idempotent_payload() -> None:
    executor = ThreadSafeExecutor()
    service = CollectionSubmissionService(executor)
    first = replace(
        command(),
        entry_type=CollectionEntryType.PASS,
        amount=None,
        note="",
        past_due_followup=PastDueFollowupInput(
            reason_code=PastDueReasonCode.PROMISED_TO_PAY_LATER,
            note="After salary",
            promised_payment_date=date(2026, 8, 2),
            promised_amount=Decimal("100.00"),
        ),
    )
    changed = replace(
        first,
        past_due_followup=PastDueFollowupInput(
            reason_code=PastDueReasonCode.PROMISED_TO_PAY_LATER,
            note="After salary",
            promised_payment_date=date(2026, 8, 3),
            promised_amount=Decimal("100.00"),
        ),
    )

    accepted = service.submit(actor=actor(), headers=headers(), command=first)
    conflict = service.submit(actor=actor(), headers=headers(), command=changed)

    assert accepted.status is CollectionStatus.ACCEPTED
    assert conflict.status is CollectionStatus.CONFLICT
    assert conflict.code == "idempotency_mismatch"
