from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.main import create_app
from gilbic_backend.management_operations_api import (
    management_operations_repository_dependency,
)
from gilbic_backend.management_operations_repository import (
    ManagementOperationAudit,
    ManagementOperationEntry,
    ManagementOperationsOverview,
    ManagementOperationsSummary,
)


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
MANAGEMENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
CLIENT_USER_ID = UUID("33333333-3333-4333-8333-333333333333")
TRANSACTION_ID = UUID("44444444-4444-4444-8444-444444444444")
EVENT_ID = UUID("55555555-5555-4555-8555-555555555555")


class FakeAuthClient:
    def get_user(self, *, access_token: str) -> AuthSession:
        return AuthSession(
            auth_user_id=AUTH_USER_ID,
            email="user@example.com",
            access_token=access_token,
            refresh_token=None,
            expires_at=None,
            email_confirmed=True,
        )


class FakeAccounts:
    def __init__(self, *, role: str) -> None:
        self.role = role

    def get_context_for_device(
        self,
        *,
        auth_user_id: UUID,
        device_identifier: str | None,
    ) -> AccountContext:
        assert auth_user_id == AUTH_USER_ID
        assert device_identifier == "test-device"
        is_management = self.role == "management"
        return AccountContext(
            user_id=MANAGEMENT_USER_ID if is_management else CLIENT_USER_ID,
            auth_user_id=AUTH_USER_ID,
            username="manager" if is_management else "client",
            email="user@example.com",
            full_name="Management" if is_management else "Client",
            status="active",
            roles=(self.role,),
            permissions=(),
            device_registered=True,
        )


class FakeOperations:
    def __init__(self) -> None:
        self.arguments: tuple[str, str, int] | None = None

    def load_overview(self, *, query: str, status: str, limit: int):
        self.arguments = (query, status, limit)
        return ManagementOperationsOverview(
            summary=ManagementOperationsSummary(
                latest_collection_date=date(2026, 8, 6),
                latest_day_amount=Decimal("50.00"),
                latest_day_payment_count=1,
                latest_day_unable_to_pay_count=0,
                unremitted_amount=Decimal("0.00"),
                unremitted_entry_count=0,
                pending_remittance_amount=Decimal("0.00"),
                pending_remittance_count=0,
                received_remittance_amount=Decimal("50.00"),
                received_remittance_count=1,
                correction_count=0,
                void_count=1,
            ),
            entries=(
                ManagementOperationEntry(
                    transaction_id=TRANSACTION_ID,
                    receipt_number="GBC-20260806-00000010",
                    collection_date=date(2026, 8, 6),
                    accepted_at=datetime(2026, 8, 6, 3, 3, tzinfo=timezone.utc),
                    client_code="TEST-REG-001",
                    client_name="TEST CLIENT REGULAR",
                    loan_number="TEST-REG-20260802",
                    loan_type_name="Regular",
                    collector_name="Test Collector",
                    entry_type="payment",
                    amount=Decimal("50.00"),
                    official_balance=Decimal("4900.00"),
                    covered_dates=(date(2026, 8, 6),),
                    edit_version=0,
                    status="received",
                    remittance_number="REM-20260805-00000004",
                    void_reason=None,
                ),
            ),
            audits=(
                ManagementOperationAudit(
                    event_id=EVENT_ID,
                    event_type="void",
                    happened_at=datetime(2026, 8, 5, 9, 1, tzinfo=timezone.utc),
                    transaction_id=TRANSACTION_ID,
                    receipt_number="GBC-20260805-00000008",
                    client_name="TEST CLIENT REGULAR",
                    loan_number="TEST-REG-20260802",
                    actor_name="Management",
                    reason="Payment posted to the wrong borrower",
                ),
            ),
        )


def headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Device-Id": "test-device",
    }


def client_with_fakes(*, role: str = "management"):
    operations = FakeOperations()
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts(
        role=role
    )
    app.dependency_overrides[management_operations_repository_dependency] = (
        lambda: operations
    )
    return TestClient(app), operations


def test_management_can_view_loan_operations() -> None:
    client, operations = client_with_fakes()

    response = client.get(
        "/api/mobile/v1/management/loan-operations?q=TEST&status=received&limit=25",
        headers=headers(),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["summary"]["latest_collection_date"] == "2026-08-06"
    assert data["summary"]["latest_day_amount"] == "50.00"
    assert data["entries"][0]["receipt_number"] == "GBC-20260806-00000010"
    assert data["entries"][0]["status"] == "received"
    assert data["entries"][0]["official_balance"] == "4900.00"
    assert data["audits"][0]["event_type"] == "void"
    assert operations.arguments == ("TEST", "received", 25)


def test_non_management_role_is_denied() -> None:
    client, _ = client_with_fakes(role="client")

    response = client.get(
        "/api/v1/management/loan-operations",
        headers=headers(),
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "management_role_required"


def test_loan_operations_has_no_write_endpoint() -> None:
    client, _ = client_with_fakes()

    response = client.post(
        "/api/v1/management/loan-operations",
        headers=headers(),
        json={"amount": "50.00"},
    )

    assert response.status_code == 405
