from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.collection_api import (
    collection_actor_dependency,
    collection_service_dependency,
)
from gilbic_backend.main import create_app
from spina_mobile_collections.contracts import (
    ActorContext,
    CollectionCommand,
    CollectionOutcome,
    CollectionStatus,
    PostedCollection,
)
from spina_mobile_collections.service import CollectionSubmissionService


KEY = UUID("6cb93829-dccd-4d43-a25c-a1f31859cc1b")
COLLECTOR_ID = UUID("11111111-1111-4111-8111-111111111111")
DEVICE_RECORD_ID = UUID("22222222-2222-4222-8222-222222222222")
CLIENT_ID = UUID("33333333-3333-4333-8333-333333333333")
LOAN_ID = UUID("44444444-4444-4444-8444-444444444444")
TRANSACTION_ID = UUID("55555555-5555-4555-8555-555555555555")
RAW_DEVICE_ID = "gilbic-installation-one"


class FixedExecutor:
    def __init__(self, status: CollectionStatus = CollectionStatus.ACCEPTED) -> None:
        self.status = status
        self.calls = 0
        self.last_actor: ActorContext | None = None
        self.last_command: CollectionCommand | None = None
        self.last_payload: dict[str, Any] | None = None

    def execute(
        self,
        *,
        actor: ActorContext,
        command: CollectionCommand,
        canonical_payload: dict[str, Any],
        request_hash: str,
    ) -> CollectionOutcome:
        assert len(request_hash) == 64
        self.calls += 1
        self.last_actor = actor
        self.last_command = command
        self.last_payload = canonical_payload
        if self.status is CollectionStatus.CONFLICT:
            return CollectionOutcome(
                status=CollectionStatus.CONFLICT,
                idempotency_key=command.idempotency_key,
                message="The loan changed. Refresh the route and review the entry.",
                code="route_revision_changed",
            )
        if self.status is CollectionStatus.REJECTED:
            return CollectionOutcome(
                status=CollectionStatus.REJECTED,
                idempotency_key=command.idempotency_key,
                message="This loan is still being checked against SPINA records.",
                code="loan_state_not_reconciled",
            )

        posted = PostedCollection(
            server_transaction_id=str(TRANSACTION_ID),
            receipt_number="GBC-20260801-00000001",
            official_balance=Decimal("800.00"),
            accepted_at=datetime(2026, 8, 1, 2, 30, tzinfo=timezone.utc),
            route_revision=f"loan:{LOAN_ID}:v8",
            message="Payment saved.",
        )
        return CollectionOutcome(
            status=self.status,
            idempotency_key=command.idempotency_key,
            message=posted.message,
            posted=posted,
        )


def actor() -> ActorContext:
    return ActorContext(
        account_id=str(COLLECTOR_ID),
        device_id=RAW_DEVICE_ID,
        registered_device_id=str(DEVICE_RECORD_ID),
        permissions=frozenset({"collection.create"}),
    )


def body(*, device_id: str = RAW_DEVICE_ID) -> dict[str, object]:
    return {
        "client_transaction_id": str(KEY),
        "route_entry_id": str(LOAN_ID),
        "client_id": str(CLIENT_ID),
        "loan_id": str(LOAN_ID),
        "collection_date": "2026-08-01",
        "entry_type": "payment",
        "amount": "200.00",
        "advance_from": None,
        "advance_until": None,
        "recorded_at": "2026-08-01T02:29:00Z",
        "device_id": device_id,
        "device_sequence": 1,
        "note": "Paid at home",
        "route_revision": f"loan:{LOAN_ID}:v7",
    }


def headers(*, device_id: str = RAW_DEVICE_ID) -> dict[str, str]:
    return {
        "Authorization": "Bearer collector-token",
        "Idempotency-Key": str(KEY),
        "X-Client-Transaction-Id": str(KEY),
        "X-Device-Id": device_id,
        "X-Gilbic-Contract-Version": "gilbic-collection-v1",
    }


def client_for(status: CollectionStatus = CollectionStatus.ACCEPTED):
    executor = FixedExecutor(status)
    service = CollectionSubmissionService(executor)
    app = create_app()
    app.dependency_overrides[collection_actor_dependency] = actor
    app.dependency_overrides[collection_service_dependency] = lambda: service
    return TestClient(app), executor


def test_payment_returns_clear_success_and_exact_currency() -> None:
    client, executor = client_for()

    response = client.post(
        "/api/v1/collector/collections",
        json=body(),
        headers=headers(),
    )

    assert response.status_code == 201, response.json()
    data = response.json()["data"]
    assert data["status"] == "accepted"
    assert data["message"] == "Payment saved."
    assert data["official_balance"] == "800.00"
    assert data["receipt_number"] == "GBC-20260801-00000001"
    assert executor.calls == 1
    assert executor.last_actor is not None
    assert executor.last_actor.storage_device_id == str(DEVICE_RECORD_ID)
    assert executor.last_payload is not None
    assert executor.last_payload["route_revision"] == f"loan:{LOAN_ID}:v7"


def test_duplicate_is_a_safe_success_not_a_second_payment() -> None:
    client, _ = client_for(CollectionStatus.DUPLICATE)

    response = client.post(
        "/api/mobile/v1/collector/collections",
        json=body(),
        headers=headers(),
    )

    assert response.status_code == 200, response.json()
    data = response.json()["data"]
    assert data["status"] == "duplicate"
    assert data["duplicate"] is True
    assert data["message"] == "Already recorded. No duplicate payment was created."


def test_changed_route_returns_refresh_instruction() -> None:
    client, _ = client_for(CollectionStatus.CONFLICT)

    response = client.post(
        "/api/v1/collector/collections",
        json=body(),
        headers=headers(),
    )

    assert response.status_code == 409, response.json()
    assert response.json()["error"]["code"] == "route_revision_changed"
    assert "Refresh the route" in response.json()["message"]


def test_unreconciled_loan_returns_plain_language_message() -> None:
    client, _ = client_for(CollectionStatus.REJECTED)

    response = client.post(
        "/api/v1/collector/collections",
        json=body(),
        headers=headers(),
    )

    assert response.status_code == 422, response.json()
    assert response.json()["error"]["code"] == "loan_state_not_reconciled"
    assert "SPINA records" in response.json()["message"]


def test_body_device_must_match_registered_request_device() -> None:
    client, executor = client_for()

    response = client.post(
        "/api/v1/collector/collections",
        json=body(device_id="another-installation"),
        headers=headers(),
    )

    assert response.status_code == 403, response.json()
    assert response.json()["error"]["code"] == "device_not_registered"
    assert executor.calls == 0
