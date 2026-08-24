from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.main import create_app
from gilbic_backend.past_due_followup_api import (
    past_due_followup_repository_dependency,
)
from gilbic_backend.past_due_followup_repository import PastDueFollowupRecord


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
COLLECTOR_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
CLIENT_ID = UUID("33333333-3333-4333-8333-333333333333")
LOAN_ID = UUID("44444444-4444-4444-8444-444444444444")
TRANSACTION_ID = UUID("55555555-5555-4555-8555-555555555555")
FOLLOWUP_ID = UUID("66666666-6666-4666-8666-666666666666")
PROMISE_ID = UUID("77777777-7777-4777-8777-777777777777")


class FakeAuthClient:
    def get_user(self, *, access_token: str) -> AuthSession:
        assert access_token == "collector-token"
        return AuthSession(
            auth_user_id=AUTH_USER_ID,
            email="collector@example.com",
            access_token=access_token,
            refresh_token=None,
            expires_at=None,
            email_confirmed=True,
        )


class FakeAccounts:
    def get_context_for_device(
        self,
        *,
        auth_user_id: UUID,
        device_identifier: str | None,
    ) -> AccountContext:
        assert auth_user_id == AUTH_USER_ID
        assert device_identifier == "device-one"
        return AccountContext(
            user_id=COLLECTOR_USER_ID,
            auth_user_id=AUTH_USER_ID,
            username="collector.one",
            email="collector@example.com",
            full_name="Collector One",
            status="active",
            roles=("collector",),
            permissions=("collection.create",),
            device_registered=True,
        )


class FakeFollowups:
    def __init__(self) -> None:
        self.request: dict[str, object] | None = None

    def create_for_collection(self, **kwargs) -> PastDueFollowupRecord:
        self.request = kwargs
        return PastDueFollowupRecord(
            id=FOLLOWUP_ID,
            client_id=CLIENT_ID,
            loan_id=LOAN_ID,
            installment_id=12,
            obligation_date=date(2026, 8, 25),
            original_past_due_amount=Decimal("40.00"),
            remaining_past_due_amount=Decimal("40.00"),
            event_kind="partial_payment",
            reason_code="promised_to_pay_later",
            reason_note="Will pay after salary",
            status="open",
            promise_id=PROMISE_ID,
            promised_payment_date=date(2026, 8, 28),
            initial_promised_amount=Decimal("20.00"),
            promised_amount=Decimal("20.00"),
            remaining_promised_amount=Decimal("20.00"),
            promise_status="pending",
            promise_version=1,
        )


def client_with_fakes() -> tuple[TestClient, FakeFollowups]:
    followups = FakeFollowups()
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts()
    app.dependency_overrides[past_due_followup_repository_dependency] = lambda: followups
    return TestClient(app), followups


def headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer collector-token",
        "X-Device-Id": "device-one",
    }


def test_collector_can_record_partial_past_due_with_simple_promise() -> None:
    client, followups = client_with_fakes()

    response = client.post(
        "/api/mobile/v1/collector/past-due-followups",
        headers=headers(),
        json={
            "source_transaction_id": str(TRANSACTION_ID),
            "installment_id": 12,
            "obligation_date": "2026-08-25",
            "past_due_amount": "40.00",
            "event_kind": "partial_payment",
            "reason": {
                "reason_code": "promised_to_pay_later",
                "note": "Will pay after salary",
                "promised_payment_date": "2026-08-28",
                "promised_amount": "20.00",
            },
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["id"] == str(FOLLOWUP_ID)
    assert data["reason_code"] == "promised_to_pay_later"
    assert data["promise"]["promised_amount"] == "20.00"
    assert data["promise"]["status"] == "pending"
    assert followups.request is not None
    assert followups.request["actor_user_id"] == COLLECTOR_USER_ID
    assert followups.request["source_transaction_id"] == TRANSACTION_ID


def test_other_reason_requires_note_at_api_boundary() -> None:
    client, _ = client_with_fakes()

    response = client.post(
        "/api/v1/collector/past-due-followups",
        headers=headers(),
        json={
            "source_transaction_id": str(TRANSACTION_ID),
            "obligation_date": "2026-08-25",
            "past_due_amount": "100.00",
            "event_kind": "unable_to_pay",
            "reason": {
                "reason_code": "other",
                "note": "",
            },
        },
    )

    assert response.status_code == 422
