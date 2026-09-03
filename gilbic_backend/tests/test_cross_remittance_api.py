from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.cross_remittance_api import (
    cross_remittance_repository_dependency,
)
from gilbic_backend.cross_remittance_repository import (
    ASSIGNED_COLLECTOR_CAPACITY,
    MANAGEMENT_CAPACITY,
    CrossRemittanceTargetRecord,
)
from gilbic_backend.main import create_app
from gilbic_backend.remittance_repository import (
    RemittanceItemRecord,
    RemittanceRecord,
    RemittanceSummaryRecord,
)


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
COLLECTOR_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
ASSIGNED_COLLECTOR_ID = UUID("33333333-3333-4333-8333-333333333333")
MANAGEMENT_USER_ID = UUID("88888888-8888-4888-8888-888888888888")
CLIENT_ID = UUID("44444444-4444-4444-8444-444444444444")
LOAN_ID = UUID("55555555-5555-4555-8555-555555555555")
TRANSACTION_ID = UUID("66666666-6666-4666-8666-666666666666")
REMITTANCE_ID = UUID("77777777-7777-4777-8777-777777777777")
COLLECTION_DATE = date(2026, 8, 3)
CREATED_AT = datetime(2026, 8, 3, 2, tzinfo=timezone.utc)


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
            permissions=("remittance.create",),
            device_registered=True,
        )


class FakeCrossRemittances:
    def __init__(self) -> None:
        self.preview_request = None
        self.submit_request = None

    def list_targets(self, *, collector_user_id: UUID, collection_date: date):
        assert collector_user_id == COLLECTOR_USER_ID
        assert collection_date == COLLECTION_DATE
        return (
            CrossRemittanceTargetRecord(
                recipient_user_id=ASSIGNED_COLLECTOR_ID,
                recipient_name="Collector Two",
                transaction_count=1,
                client_count=1,
                total_amount=Decimal("200.00"),
                recipient_capacity=ASSIGNED_COLLECTOR_CAPACITY,
            ),
            CrossRemittanceTargetRecord(
                recipient_user_id=MANAGEMENT_USER_ID,
                recipient_name="Management One",
                transaction_count=1,
                client_count=1,
                total_amount=Decimal("200.00"),
                recipient_capacity=MANAGEMENT_CAPACITY,
            ),
        )

    def preview(
        self,
        *,
        collector_user_id: UUID,
        recipient_user_id: UUID,
        recipient_capacity: str,
        collection_date: date,
    ) -> RemittanceSummaryRecord:
        self.preview_request = (
            collector_user_id,
            recipient_user_id,
            recipient_capacity,
            collection_date,
        )
        return _summary()

    def submit(
        self,
        *,
        collector_user_id: UUID,
        recipient_user_id: UUID,
        recipient_capacity: str,
        collection_date: date,
        note: str,
    ) -> RemittanceRecord:
        self.submit_request = (
            collector_user_id,
            recipient_user_id,
            recipient_capacity,
            collection_date,
            note,
        )
        recipient_name = (
            "Management One"
            if recipient_capacity == MANAGEMENT_CAPACITY
            else "Collector Two"
        )
        return RemittanceRecord(
            remittance_id=REMITTANCE_ID,
            remittance_number="REM-20260803-00000001",
            collector_user_id=COLLECTOR_USER_ID,
            collector_name="Collector One",
            recipient_user_id=recipient_user_id,
            recipient_name=recipient_name,
            collection_date=COLLECTION_DATE,
            status="submitted",
            transaction_count=1,
            payment_count=1,
            unable_to_pay_count=0,
            covered_payment_count=0,
            client_count=1,
            total_amount=Decimal("200.00"),
            note=note,
            submitted_at=CREATED_AT,
            received_at=None,
            items=_summary().items,
        )


def _summary() -> RemittanceSummaryRecord:
    item = RemittanceItemRecord(
        transaction_id=TRANSACTION_ID,
        client_id=CLIENT_ID,
        client_name="Ana Client",
        loan_id=LOAN_ID,
        loan_type="Regular",
        collection_date=COLLECTION_DATE,
        entry_type="payment",
        amount=Decimal("200.00"),
        receipt_number="GBC-20260803-00000001",
        accepted_at=CREATED_AT,
        note="",
        covered_dates=(COLLECTION_DATE,),
    )
    return RemittanceSummaryRecord(
        collection_date=COLLECTION_DATE,
        collector_user_id=COLLECTOR_USER_ID,
        collector_name="Collector One",
        transaction_count=1,
        payment_count=1,
        unable_to_pay_count=0,
        covered_payment_count=0,
        client_count=1,
        total_amount=Decimal("200.00"),
        items=(item,),
    )


def _client() -> tuple[TestClient, FakeCrossRemittances]:
    remittances = FakeCrossRemittances()
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts()
    app.dependency_overrides[cross_remittance_repository_dependency] = (
        lambda: remittances
    )
    return TestClient(app), remittances


def _headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer collector-token",
        "X-Device-Id": "device-one",
    }


def test_cross_remittance_targets_show_assigned_collector_and_management() -> None:
    client, _ = _client()

    response = client.get(
        "/api/mobile/v1/collector/cross-remittances/targets"
        f"?collection_date={COLLECTION_DATE.isoformat()}",
        headers=_headers(),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 2
    assert data[0]["recipient_user_id"] == str(ASSIGNED_COLLECTOR_ID)
    assert data[0]["recipient_capacity"] == ASSIGNED_COLLECTOR_CAPACITY
    assert data[0]["role_name"] == "Assigned Collector"
    assert data[0]["total_amount"] == "200.00"
    assert data[1]["recipient_user_id"] == str(MANAGEMENT_USER_ID)
    assert data[1]["recipient_capacity"] == MANAGEMENT_CAPACITY
    assert data[1]["role_name"] == "Management"
    assert data[1]["total_amount"] == "200.00"


def test_cross_remittance_preview_forwards_management_capacity() -> None:
    client, remittances = _client()

    response = client.get(
        "/api/mobile/v1/collector/cross-remittances/preview"
        f"?recipient_user_id={MANAGEMENT_USER_ID}"
        f"&recipient_capacity={MANAGEMENT_CAPACITY}"
        f"&collection_date={COLLECTION_DATE.isoformat()}",
        headers=_headers(),
    )

    assert response.status_code == 200
    assert response.json()["data"]["total_amount"] == "200.00"
    assert remittances.preview_request == (
        COLLECTOR_USER_ID,
        MANAGEMENT_USER_ID,
        MANAGEMENT_CAPACITY,
        COLLECTION_DATE,
    )


def test_cross_remittance_submission_preserves_selected_management_capacity() -> None:
    client, remittances = _client()

    response = client.post(
        "/api/mobile/v1/collector/cross-remittances",
        headers=_headers(),
        json={
            "recipient_user_id": str(MANAGEMENT_USER_ID),
            "recipient_capacity": MANAGEMENT_CAPACITY,
            "collection_date": COLLECTION_DATE.isoformat(),
            "note": "Cash handed directly to Management",
        },
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["recipient_capacity"] == MANAGEMENT_CAPACITY
    assert data["recipient_role"] == "Management"
    assert data["status"] == "submitted"
    assert "without creating another payment transaction" in data["acceptance_message"]
    assert remittances.submit_request == (
        COLLECTOR_USER_ID,
        MANAGEMENT_USER_ID,
        MANAGEMENT_CAPACITY,
        COLLECTION_DATE,
        "Cash handed directly to Management",
    )
