from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.greenfield_regular_eir_anchor_api import (
    greenfield_regular_eir_anchor_repository_dependency,
)
from gilbic_backend.greenfield_regular_eir_anchor_repository import (
    GreenfieldRegularEirAnchorError,
    GreenfieldRegularEirAnchorRecord,
)
from gilbic_backend.main import create_app


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
MANAGEMENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
CLIENT_ID = UUID("33333333-3333-4333-8333-333333333333")
LOAN_ID = UUID("44444444-4444-4444-8444-444444444444")
POSTING_ID = UUID("55555555-5555-4555-8555-555555555555")
DISBURSEMENT_EVENT_ID = UUID("66666666-6666-4666-8666-666666666666")
JOURNAL_ENTRY_ID = UUID("77777777-7777-4777-8777-777777777777")
SCHEDULE_ID = UUID("88888888-8888-4888-8888-888888888888")


class FakeAuthClient:
    def get_user(self, *, access_token: str) -> AuthSession:
        assert access_token == "management-token"
        return AuthSession(
            auth_user_id=AUTH_USER_ID,
            email="management@example.com",
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
        assert device_identifier == "management-device"
        return AccountContext(
            user_id=MANAGEMENT_USER_ID,
            auth_user_id=AUTH_USER_ID,
            username="management.one",
            email="management@example.com",
            full_name="Management One",
            status="active",
            roles=("management",),
            permissions=("accounting.view",),
            device_registered=True,
        )


class FakeAnchorRepository:
    def __init__(self) -> None:
        self.request: dict[str, object] | None = None
        self.error: Exception | None = None

    def list_readiness(self, **kwargs):
        self.request = kwargs
        if self.error is not None:
            raise self.error
        return (
            GreenfieldRegularEirAnchorRecord(
                posting_id=POSTING_ID,
                disbursement_event_id=DISBURSEMENT_EVENT_ID,
                loan_id=LOAN_ID,
                loan_number="LN-0001",
                client_id=CLIENT_ID,
                client_code="C-0001",
                client_name="Test Borrower",
                journal_entry_id=JOURNAL_ENTRY_ID,
                entry_number="JE-202608-00000001",
                release_source_event_key=f"loan_disbursement:{DISBURSEMENT_EVENT_ID}",
                anchor_date=date(2026, 8, 12),
                disbursed_at=datetime(2026, 8, 12, 2, 0, tzinfo=timezone.utc),
                initial_gross_carrying_amount=Decimal("5000.00"),
                initial_loan_component=Decimal("5000.00"),
                initial_accrued_interest_component=Decimal("0.00"),
                schedule_id=SCHEDULE_ID,
                schedule_version=1,
                schedule_status="active",
                payment_frequency="daily",
                contract_reference="CONTRACT-0001",
                contract_signed_date=date(2026, 8, 12),
                schedule_effective_from=date(2026, 8, 12),
                registration_id=1,
                evidence_basis="signed_contract",
                evidence_reference="SIGNED-0001",
                installment_count=120,
                first_due_date=date(2026, 8, 13),
                contractual_due_date=date(2026, 12, 10),
                contractual_cash_total=Decimal("6000.00"),
                daily_eir=Decimal("0.003137297107"),
                daily_eir_percent=Decimal("0.31372971"),
                pre_anchor_collection_count=0,
                same_day_collection_count=0,
                readiness_status="greenfield_regular_eir_anchor_ready",
                anchor_source_key=f"greenfield_regular_eir_anchor:{POSTING_ID}",
                anchor_policy_version="greenfield_regular_eir_anchor_v1",
                collection_journal_integration_enabled=False,
                journal_lines_enabled=False,
                automatic_source_posting=False,
            ),
        )


def client_with_fakes() -> tuple[TestClient, FakeAnchorRepository]:
    repository = FakeAnchorRepository()
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts()
    app.dependency_overrides[greenfield_regular_eir_anchor_repository_dependency] = (
        lambda: repository
    )
    return TestClient(app), repository


def headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer management-token",
        "X-Device-Id": "management-device",
    }


def test_management_can_read_greenfield_regular_eir_anchor_readiness() -> None:
    client, repository = client_with_fakes()
    response = client.get(
        "/api/v1/management/accounting/regular-greenfield-anchors/readiness",
        params={
            "readiness_status": "greenfield_regular_eir_anchor_ready",
            "loan_id": str(LOAN_ID),
            "limit": 25,
        },
        headers=headers(),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["anchor_policy_version"] == "greenfield_regular_eir_anchor_v1"
    assert data["collection_journal_integration_enabled"] is False
    assert data["journal_lines_enabled"] is False
    assert data["automatic_source_posting"] is False
    anchor = data["anchors"][0]
    assert anchor["posting_id"] == str(POSTING_ID)
    assert anchor["loan_id"] == str(LOAN_ID)
    assert anchor["schedule_id"] == str(SCHEDULE_ID)
    assert anchor["initial_gross_carrying_amount"] == "5000.00"
    assert anchor["initial_accrued_interest_component"] == "0.00"
    assert anchor["contractual_cash_total"] == "6000.00"
    assert anchor["readiness_status"] == "greenfield_regular_eir_anchor_ready"
    assert anchor["collection_journal_integration_enabled"] is False
    assert anchor["journal_lines_enabled"] is False
    assert anchor["automatic_source_posting"] is False
    assert repository.request == {
        "readiness_status": "greenfield_regular_eir_anchor_ready",
        "loan_id": LOAN_ID,
        "limit": 25,
    }


def test_greenfield_anchor_repository_error_is_fail_closed() -> None:
    client, repository = client_with_fakes()
    repository.error = GreenfieldRegularEirAnchorError(
        "Greenfield Regular EIR anchor evidence is unavailable."
    )
    response = client.get(
        "/api/v1/management/accounting/regular-greenfield-anchors/readiness",
        headers=headers(),
    )
    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "greenfield_regular_eir_anchor_error",
        "message": "Greenfield Regular EIR anchor evidence is unavailable.",
    }
