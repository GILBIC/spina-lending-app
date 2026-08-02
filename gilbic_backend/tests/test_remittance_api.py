from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.main import create_app
from gilbic_backend.remittance_api import remittance_repository_dependency
from gilbic_backend.remittance_repository import (
    RemittanceItemRecord,
    RemittanceRecord,
    RemittanceRecipientRecord,
    RemittanceSummaryRecord,
)


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
COLLECTOR_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
RECIPIENT_USER_ID = UUID("33333333-3333-4333-8333-333333333333")
CLIENT_ID = UUID("44444444-4444-4444-8444-444444444444")
LOAN_ID = UUID("55555555-5555-4555-8555-555555555555")
TRANSACTION_ID = UUID("66666666-6666-4666-8666-666666666666")
REMITTANCE_ID = UUID("77777777-7777-4777-8777-777777777777")
COLLECTION_DATE = date(2026, 8, 2)
SUBMITTED_AT = datetime(2026, 8, 2, 8, tzinfo=timezone.utc)


class FakeAuthClient:
    def get_user(self, *, access_token: str) -> AuthSession:
        assert access_token == "session-token"
        return AuthSession(
            auth_user_id=AUTH_USER_ID,
            email="user@example.com",
            access_token=access_token,
            refresh_token=None,
            expires_at=None,
            email_confirmed=True,
        )


class FakeAccounts:
    def __init__(self, *, user_id: UUID, permissions: tuple[str, ...]) -> None:
        self.user_id = user_id
        self.permissions = permissions

    def get_context_for_device(
        self,
        *,
        auth_user_id: UUID,
        device_identifier: str | None,
    ) -> AccountContext:
        assert auth_user_id == AUTH_USER_ID
        assert device_identifier == "device-one"
        return AccountContext(
            user_id=self.user_id,
            auth_user_id=AUTH_USER_ID,
            username="test.user",
            email="user@example.com",
            full_name="Test User",
            status="active",
            roles=("collector",),
            permissions=self.permissions,
            device_registered=True,
        )


class FakeRemittances:
    def __init__(self) -> None:
        self.submit_request: dict[str, object] | None = None
        self.received_request: dict[str, object] | None = None

    def list_recipients(self, *, actor_user_id: UUID):
        assert actor_user_id == COLLECTOR_USER_ID
        return (
            RemittanceRecipientRecord(
                user_id=RECIPIENT_USER_ID,
                full_name="Office Staff",
                role_name="Employee",
            ),
        )

    def preview(self, *, collector_user_id: UUID, collection_date: date):
        assert collector_user_id == COLLECTOR_USER_ID
        assert collection_date == COLLECTION_DATE
        return _summary()

    def submit(self, **kwargs):
        self.submit_request = kwargs
        return _record(status="submitted", received_at=None)

    def list_for_user(self, *, actor_user_id: UUID):
        assert actor_user_id in {COLLECTOR_USER_ID, RECIPIENT_USER_ID}
        return (_record(status="submitted", received_at=None),)

    def confirm_received(self, **kwargs):
        self.received_request = kwargs
        return _record(
            status="received",
            received_at=datetime(2026, 8, 2, 9, tzinfo=timezone.utc),
        )


def _item() -> RemittanceItemRecord:
    return RemittanceItemRecord(
        transaction_id=TRANSACTION_ID,
        client_id=CLIENT_ID,
        client_name="Ana Client",
        loan_id=LOAN_ID,
        loan_type="Regular",
        collection_date=COLLECTION_DATE,
        entry_type="advance",
        amount=Decimal("100.00"),
        receipt_number="GBC-20260802-00000001",
        accepted_at=SUBMITTED_AT,
        note="Selected dates",
        covered_dates=(COLLECTION_DATE, date(2026, 8, 4)),
    )


def _summary() -> RemittanceSummaryRecord:
    return RemittanceSummaryRecord(
        collection_date=COLLECTION_DATE,
        collector_user_id=COLLECTOR_USER_ID,
        collector_name="Collector One",
        transaction_count=1,
        payment_count=1,
        unable_to_pay_count=0,
        covered_payment_count=1,
        client_count=1,
        total_amount=Decimal("100.00"),
        items=(_item(),),
    )


def _record(*, status: str, received_at: datetime | None) -> RemittanceRecord:
    summary = _summary()
    return RemittanceRecord(
        remittance_id=REMITTANCE_ID,
        remittance_number="REM-20260802-00000001",
        collector_user_id=COLLECTOR_USER_ID,
        collector_name="Collector One",
        recipient_user_id=RECIPIENT_USER_ID,
        recipient_name="Office Staff",
        collection_date=COLLECTION_DATE,
        status=status,
        transaction_count=summary.transaction_count,
        payment_count=summary.payment_count,
        unable_to_pay_count=summary.unable_to_pay_count,
        covered_payment_count=summary.covered_payment_count,
        client_count=summary.client_count,
        total_amount=summary.total_amount,
        note="Daily cash",
        submitted_at=SUBMITTED_AT,
        received_at=received_at,
        items=summary.items,
    )


def client_with_fakes(
    *,
    user_id: UUID,
    permissions: tuple[str, ...],
) -> tuple[TestClient, FakeRemittances]:
    remittances = FakeRemittances()
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts(
        user_id=user_id,
        permissions=permissions,
    )
    app.dependency_overrides[remittance_repository_dependency] = lambda: remittances
    return TestClient(app), remittances


def headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer session-token",
        "X-Device-Id": "device-one",
    }


def test_collector_preview_and_submit_use_server_calculated_summary() -> None:
    client, remittances = client_with_fakes(
        user_id=COLLECTOR_USER_ID,
        permissions=("remittance.create", "remittance.view"),
    )

    preview = client.get(
        "/api/mobile/v1/collector/remittances/preview",
        params={"collection_date": COLLECTION_DATE.isoformat()},
        headers=headers(),
    )
    response = client.post(
        "/api/mobile/v1/collector/remittances",
        headers=headers(),
        json={
            "recipient_user_id": str(RECIPIENT_USER_ID),
            "collection_date": COLLECTION_DATE.isoformat(),
            "note": "Daily cash",
        },
    )

    assert preview.status_code == 200
    assert preview.json()["data"]["total_amount"] == "100.00"
    assert preview.json()["data"]["covered_payment_count"] == 1
    assert preview.json()["data"]["items"][0]["covered_dates"] == [
        "2026-08-02",
        "2026-08-04",
    ]
    assert response.status_code == 201
    assert response.json()["data"]["remittance_number"] == "REM-20260802-00000001"
    assert response.json()["data"]["status"] == "submitted"
    assert remittances.submit_request is not None
    assert remittances.submit_request["collector_user_id"] == COLLECTOR_USER_ID
    assert remittances.submit_request["recipient_user_id"] == RECIPIENT_USER_ID


def test_selected_recipient_can_confirm_received() -> None:
    client, remittances = client_with_fakes(
        user_id=RECIPIENT_USER_ID,
        permissions=("remittance.view", "remittance.receive"),
    )

    response = client.post(
        f"/api/mobile/v1/remittances/{REMITTANCE_ID}/receive",
        headers=headers(),
    )

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "received"
    assert response.json()["data"]["received_at"] is not None
    assert remittances.received_request == {
        "remittance_id": REMITTANCE_ID,
        "recipient_user_id": RECIPIENT_USER_ID,
    }
