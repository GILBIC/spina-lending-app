from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.activity_notification_api import (
    activity_notification_repository_dependency,
)
from gilbic_backend.activity_notification_repository import ActivityNotificationRecord
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.main import create_app


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
RECIPIENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
SENDER_USER_ID = UUID("33333333-3333-4333-8333-333333333333")
TRANSACTION_ID = UUID("44444444-4444-4444-8444-444444444444")
NOTIFICATION_ID = UUID("55555555-5555-4555-8555-555555555555")
CREATED_AT = datetime(2026, 8, 3, 1, tzinfo=timezone.utc)


class FakeAuthClient:
    def get_user(self, *, access_token: str) -> AuthSession:
        assert access_token == "activity-token"
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
            user_id=RECIPIENT_USER_ID,
            auth_user_id=AUTH_USER_ID,
            username="collector.one",
            email="collector@example.com",
            full_name="Collector One",
            status="active",
            roles=("collector",),
            permissions=("route.view",),
            device_registered=True,
        )


class FakeActivityNotifications:
    def __init__(self) -> None:
        self.read_request: tuple[UUID, UUID] | None = None

    def list_for_user(self, *, recipient_user_id: UUID, limit: int):
        assert recipient_user_id == RECIPIENT_USER_ID
        assert limit == 25
        return (self._record(),)

    def mark_read(
        self,
        *,
        notification_id: UUID,
        recipient_user_id: UUID,
    ) -> ActivityNotificationRecord:
        self.read_request = (notification_id, recipient_user_id)
        return self._record(read=True)

    def _record(self, *, read: bool = False) -> ActivityNotificationRecord:
        return ActivityNotificationRecord(
            notification_id=NOTIFICATION_ID,
            recipient_user_id=RECIPIENT_USER_ID,
            sender_user_id=SENDER_USER_ID,
            sender_name="Collector Two",
            notification_type="cross_collection_posted",
            title="Payment recorded by another collector",
            message="Collector Two posted a payment.",
            transaction_id=TRANSACTION_ID,
            remittance_id=None,
            client_id=None,
            metadata={"receipt_number": "GBC-20260803-00000001"},
            is_read=read,
            created_at=CREATED_AT,
            read_at=CREATED_AT if read else None,
        )


def client_with_fakes() -> tuple[TestClient, FakeActivityNotifications]:
    notifications = FakeActivityNotifications()
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts()
    app.dependency_overrides[activity_notification_repository_dependency] = (
        lambda: notifications
    )
    return TestClient(app), notifications


def headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer activity-token",
        "X-Device-Id": "device-one",
    }


def test_any_authenticated_active_account_can_list_its_activity_notifications() -> None:
    client, _ = client_with_fakes()

    response = client.get(
        "/api/mobile/v1/activity-notifications?limit=25",
        headers=headers(),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["notification_id"] == str(NOTIFICATION_ID)
    assert data[0]["notification_type"] == "cross_collection_posted"
    assert data[0]["sender_name"] == "Collector Two"
    assert data[0]["metadata"]["receipt_number"] == "GBC-20260803-00000001"
    assert data[0]["is_read"] is False


def test_notification_owner_can_mark_activity_read() -> None:
    client, notifications = client_with_fakes()

    response = client.post(
        f"/api/mobile/v1/activity-notifications/{NOTIFICATION_ID}/read",
        headers=headers(),
    )

    assert response.status_code == 200
    assert response.json()["data"]["is_read"] is True
    assert notifications.read_request == (NOTIFICATION_ID, RECIPIENT_USER_ID)
