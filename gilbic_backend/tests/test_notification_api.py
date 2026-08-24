from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.main import create_app
from gilbic_backend.notification_api import (
    notification_remittance_repository_dependency,
    notification_repository_dependency,
)
from gilbic_backend.notification_repository import RemittanceNotificationRecord
from gilbic_backend.remittance_repository import RemittanceRecord


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
RECIPIENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
COLLECTOR_USER_ID = UUID("33333333-3333-4333-8333-333333333333")
REMITTANCE_ID = UUID("44444444-4444-4444-8444-444444444444")
NOTIFICATION_ID = UUID("55555555-5555-4555-8555-555555555555")
CREATED_AT = datetime(2026, 8, 2, 8, tzinfo=timezone.utc)


class FakeAuthClient:
    def get_user(self, *, access_token: str) -> AuthSession:
        assert access_token == "recipient-token"
        return AuthSession(
            auth_user_id=AUTH_USER_ID,
            email="recipient@example.com",
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
            user_id=RECIPIENT_USER_ID,
            auth_user_id=AUTH_USER_ID,
            username="office.one",
            email="recipient@example.com",
            full_name="Office Staff",
            status="active",
            roles=("employee",),
            permissions=("remittance.view", "remittance.receive"),
            device_registered=True,
        )


class FakeNotifications:
    def __init__(self) -> None:
        self.accepted = False
        self.read_request: tuple[UUID, UUID] | None = None

    def list_for_user(self, *, recipient_user_id: UUID):
        assert recipient_user_id == RECIPIENT_USER_ID
        return (self._record(),)

    def get_for_user(
        self,
        *,
        notification_id: UUID,
        recipient_user_id: UUID,
    ) -> RemittanceNotificationRecord:
        assert notification_id == NOTIFICATION_ID
        assert recipient_user_id == RECIPIENT_USER_ID
        return self._record()

    def mark_read(
        self,
        *,
        notification_id: UUID,
        recipient_user_id: UUID,
    ) -> RemittanceNotificationRecord:
        self.read_request = (notification_id, recipient_user_id)
        return self._record(read_at=CREATED_AT)

    def _record(
        self,
        *,
        read_at: datetime | None = None,
    ) -> RemittanceNotificationRecord:
        accepted_at = CREATED_AT if self.accepted else None
        return RemittanceNotificationRecord(
            notification_id=NOTIFICATION_ID,
            recipient_user_id=RECIPIENT_USER_ID,
            sender_user_id=COLLECTOR_USER_ID,
            remittance_id=REMITTANCE_ID,
            title="Remittance awaiting acceptance",
            message="Collector One sent PHP 100.00.",
            status="accepted" if self.accepted else "pending",
            created_at=CREATED_AT,
            read_at=read_at or accepted_at,
            accepted_at=accepted_at,
            remittance_number="REM-20260802-00000001",
            collector_name="Collector One",
            total_amount=Decimal("100.00"),
            client_count=1,
            transaction_count=1,
            collection_date=date(2026, 8, 2),
        )


class FakeRemittances:
    def __init__(self, notifications: FakeNotifications) -> None:
        self.notifications = notifications
        self.request: dict[str, object] | None = None

    def confirm_received(self, **kwargs) -> RemittanceRecord:
        self.request = kwargs
        self.notifications.accepted = True
        return RemittanceRecord(
            remittance_id=REMITTANCE_ID,
            remittance_number="REM-20260802-00000001",
            collector_user_id=COLLECTOR_USER_ID,
            collector_name="Collector One",
            recipient_user_id=RECIPIENT_USER_ID,
            recipient_name="Office Staff",
            collection_date=date(2026, 8, 2),
            status="received",
            transaction_count=1,
            payment_count=1,
            unable_to_pay_count=0,
            covered_payment_count=0,
            client_count=1,
            total_amount=Decimal("100.00"),
            note="",
            submitted_at=CREATED_AT,
            received_at=CREATED_AT,
            items=(),
        )


def client_with_fakes() -> tuple[TestClient, FakeNotifications, FakeRemittances]:
    notifications = FakeNotifications()
    remittances = FakeRemittances(notifications)
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts()
    app.dependency_overrides[notification_repository_dependency] = (
        lambda: notifications
    )
    app.dependency_overrides[notification_remittance_repository_dependency] = (
        lambda: remittances
    )
    return TestClient(app), notifications, remittances


def headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer recipient-token",
        "X-Device-Id": "device-one",
    }


def test_recipient_receives_reviewable_remittance_notification() -> None:
    client, _, _ = client_with_fakes()

    response = client.get(
        "/api/mobile/v1/notifications",
        headers=headers(),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["notification_id"] == str(NOTIFICATION_ID)
    assert data[0]["action_code"] == "review_remittance"
    assert data[0]["is_pending"] is True
    assert data[0]["title"] == "Remittance awaiting acceptance"
    assert data[0]["message"] == "Collector One sent PHP 100.00."
    assert data[0]["custody_message"] == (
        "Review every payment, then confirm only after you physically receive the cash."
    )


def test_accepting_notification_requires_review_acknowledgement() -> None:
    client, notifications, remittances = client_with_fakes()

    response = client.post(
        f"/api/mobile/v1/notifications/{NOTIFICATION_ID}/accept-remittance",
        headers=headers(),
        json={"review_acknowledged": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == (
        "Remittance accepted. The money is now under your custody."
    )
    assert body["data"]["status"] == "received"
    assert body["data"]["custody_user_id"] == str(RECIPIENT_USER_ID)
    notification = body["data"]["notification"]
    assert notification["status"] == "accepted"
    assert notification["is_pending"] is False
    assert notification["title"] == "Remittance accepted"
    assert notification["message"] == (
        "REM-20260802-00000001 was accepted. "
        "Money is now under your custody."
    )
    assert notification["custody_message"] == (
        "Money is now under your custody."
    )
    assert remittances.request == {
        "remittance_id": REMITTANCE_ID,
        "recipient_user_id": RECIPIENT_USER_ID,
        "review_acknowledged": True,
    }
    assert notifications.accepted is True
