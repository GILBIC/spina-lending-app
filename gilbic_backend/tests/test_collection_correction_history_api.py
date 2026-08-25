from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.collection_correction_api import (
    correction_history_repository_dependency,
)
from gilbic_backend.collection_correction_history_repository import (
    CollectionCorrectionHistoryRecord,
)
from gilbic_backend.collection_correction_repository import CollectionCorrectionForbidden
from gilbic_backend.main import create_app


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
COLLECTOR_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
TRANSACTION_ID = UUID("33333333-3333-4333-8333-333333333333")
EDIT_ID = UUID("44444444-4444-4444-8444-444444444444")


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
            permissions=("collection.correct.own_unremitted",),
            device_registered=True,
        )


class FakeHistory:
    def __init__(self) -> None:
        self.error: Exception | None = None
        self.request: dict[str, object] | None = None

    def list_for_transaction(self, **kwargs):
        if self.error is not None:
            raise self.error
        self.request = kwargs
        return (
            CollectionCorrectionHistoryRecord(
                edit_id=EDIT_ID,
                transaction_id=TRANSACTION_ID,
                edit_version=2,
                reason="Wrong amount",
                previous_snapshot={"amount": "100.00", "entry_type": "payment"},
                replacement_snapshot={"amount": "80.00", "entry_type": "payment"},
                previous_covered_dates=(date(2026, 8, 24),),
                replacement_covered_dates=(date(2026, 8, 24),),
                edited_by_user_id=COLLECTOR_USER_ID,
                edited_by_name="Collector One",
                edited_at=datetime(2026, 8, 25, 1, 30, tzinfo=timezone.utc),
            ),
        )


def headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer collector-token",
        "X-Device-Id": "device-one",
    }


def client_with_fake():
    history = FakeHistory()
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts()
    app.dependency_overrides[correction_history_repository_dependency] = lambda: history
    return TestClient(app), history


def test_collector_can_read_immutable_correction_history() -> None:
    client, history = client_with_fake()

    response = client.get(
        f"/api/mobile/v1/collector/collections/{TRANSACTION_ID}/corrections",
        headers=headers(),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["transaction_id"] == str(TRANSACTION_ID)
    assert data["corrections"][0]["edit_version"] == 2
    assert data["corrections"][0]["reason"] == "Wrong amount"
    assert data["corrections"][0]["previous_snapshot"]["amount"] == "100.00"
    assert data["corrections"][0]["replacement_snapshot"]["amount"] == "80.00"
    assert data["corrections"][0]["edited_by_name"] == "Collector One"
    assert history.request == {
        "actor_user_id": COLLECTOR_USER_ID,
        "transaction_id": TRANSACTION_ID,
    }


def test_correction_history_preserves_repository_authority_check() -> None:
    client, history = client_with_fake()
    history.error = CollectionCorrectionForbidden("Not your collection history.")

    response = client.get(
        f"/api/v1/collector/collections/{TRANSACTION_ID}/corrections",
        headers=headers(),
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "collection_correction_forbidden"
