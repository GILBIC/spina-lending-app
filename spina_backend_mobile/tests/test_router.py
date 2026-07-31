from __future__ import annotations

import threading
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from spina_mobile_collections.contracts import (
    ActorContext,
    CollectionCommand,
    CollectionOutcome,
    CollectionStatus,
    PostedCollection,
)
from spina_mobile_collections.router import create_collection_router
from spina_mobile_collections.service import CollectionSubmissionService

KEY = "6cb93829-dccd-4d43-a25c-a1f31859cc1b"


class ReplayExecutor:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stored: tuple[str, PostedCollection] | None = None

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
            if self._stored is not None:
                stored_hash, posted = self._stored
                if stored_hash != request_hash:
                    return CollectionOutcome(
                        status=CollectionStatus.CONFLICT,
                        idempotency_key=command.idempotency_key,
                        message="The route changed after download.",
                        code="idempotency_mismatch",
                    )
                return CollectionOutcome(
                    status=CollectionStatus.DUPLICATE,
                    idempotency_key=command.idempotency_key,
                    message="Previously accepted",
                    posted=posted,
                )

            posted = PostedCollection(
                server_transaction_id="collection-9001",
                receipt_number="OR-00009001",
                official_balance=Decimal("4600.00"),
                accepted_at=datetime(2026, 7, 31, 5, 16, 2, tzinfo=timezone.utc),
                route_revision="route-v4",
            )
            self._stored = (request_hash, posted)
            return CollectionOutcome(
                status=CollectionStatus.ACCEPTED,
                idempotency_key=command.idempotency_key,
                message="Collection accepted",
                posted=posted,
            )


def build_client() -> TestClient:
    executor = ReplayExecutor()
    service = CollectionSubmissionService(executor)

    def get_actor() -> ActorContext:
        return ActorContext(
            account_id="collector-7",
            device_id="collector-phone-15",
            permissions=frozenset({"collection.create"}),
        )

    def get_service() -> CollectionSubmissionService:
        return service

    app = FastAPI()
    app.include_router(
        create_collection_router(
            get_actor=get_actor,
            get_service=get_service,
        )
    )
    return TestClient(app)


def body(*, amount: float = 200.0) -> dict[str, object]:
    return {
        "client_transaction_id": KEY,
        "route_entry_id": "route-entry-304",
        "client_id": "client-304",
        "loan_id": "loan-815",
        "collection_date": "2026-07-31",
        "entry_type": "payment",
        "amount": amount,
        "advance_from": None,
        "advance_until": None,
        "recorded_at": "2026-07-31T05:15:00Z",
        "device_id": "collector-phone-15",
        "device_sequence": 45,
        "note": "Paid at home",
        "route_revision": "route-v3",
    }


def request_headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "Idempotency-Key": KEY,
        "X-Client-Transaction-Id": KEY,
        "X-Device-Id": "collector-phone-15",
        "X-Gilbic-Contract-Version": "gilbic-collection-v1",
    }


def test_endpoint_accepts_then_replays_original_receipt() -> None:
    client = build_client()

    accepted = client.post(
        "/api/mobile/v1/collector/collections",
        json=body(),
        headers=request_headers(),
    )
    replayed = client.post(
        "/api/mobile/v1/collector/collections",
        json=body(),
        headers=request_headers(),
    )

    assert accepted.status_code == 201
    assert accepted.json()["data"]["status"] == "accepted"
    assert accepted.json()["data"]["receipt_number"] == "OR-00009001"
    assert replayed.status_code == 200
    assert replayed.json()["data"]["status"] == "duplicate"
    assert replayed.json()["data"]["receipt_number"] == "OR-00009001"


def test_endpoint_rejects_changed_payload_with_same_key() -> None:
    client = build_client()
    client.post(
        "/api/mobile/v1/collector/collections",
        json=body(),
        headers=request_headers(),
    )

    conflict = client.post(
        "/api/mobile/v1/collector/collections",
        json=body(amount=250.0),
        headers=request_headers(),
    )

    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_mismatch"


def test_endpoint_rejects_unsupported_contract_version() -> None:
    client = build_client()
    changed_headers = request_headers()
    changed_headers["X-Gilbic-Contract-Version"] = "gilbic-collection-v2"

    response = client.post(
        "/api/mobile/v1/collector/collections",
        json=body(),
        headers=changed_headers,
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsupported_contract_version"


def test_endpoint_rejects_header_and_body_key_mismatch() -> None:
    client = build_client()
    changed_body = body()
    changed_body["client_transaction_id"] = str(
        UUID("d35d95eb-7481-4f20-a2dd-f0cb13e3953e")
    )

    response = client.post(
        "/api/mobile/v1/collector/collections",
        json=changed_body,
        headers=request_headers(),
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "idempotency_key_mismatch"
