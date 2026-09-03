from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from gilbic_backend import management_no_collection_announcement
from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.main import create_app
from gilbic_backend.management_no_collection_api import (
    management_no_collection_query_repository_dependency,
)
from gilbic_backend.management_no_collection_query_repository import (
    ActiveNoCollectionState,
    NoCollectionInstallmentState,
    NoCollectionLoanState,
)


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
MANAGEMENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
CLIENT_ID = UUID("33333333-3333-4333-8333-333333333333")
LOAN_ID = UUID("44444444-4444-4444-8444-444444444444")
SCHEDULE_ID = UUID("55555555-5555-4555-8555-555555555555")
ADJUSTMENT_ID = UUID("66666666-6666-4666-8666-666666666666")


def _fixed_business_date() -> date:
    return date(2026, 8, 15)


@pytest.fixture(autouse=True)
def _freeze_business_date(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        management_no_collection_announcement,
        "philippines_business_date",
        _fixed_business_date,
    )


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
            permissions=("lending.no_collection.manage",),
            device_registered=True,
        )


class FakeQueryRepository:
    def __init__(self) -> None:
        self.seen_loan_id: UUID | None = None

    def get_loan_state(self, *, loan_id: UUID) -> NoCollectionLoanState:
        self.seen_loan_id = loan_id
        return NoCollectionLoanState(
            loan_id=LOAN_ID,
            loan_number="SPN-1001",
            client_id=CLIENT_ID,
            client_name="Ana Client",
            loan_type="Regular",
            schedule_id=SCHEDULE_ID,
            schedule_version=2,
            payment_frequency="daily",
            contract_reference="CTR-1001",
            operational_version=3,
            semi_monthly_days=(15, 30),
            installments=(
                NoCollectionInstallmentState(
                    installment_id=10,
                    installment_number=5,
                    contractual_due_date=date(2026, 8, 16),
                    effective_due_date=date(2026, 8, 16),
                    contractual_amount=Decimal("200.00"),
                    allocated_amount=Decimal("0.00"),
                    last_adjustment_id=None,
                ),
                NoCollectionInstallmentState(
                    installment_id=11,
                    installment_number=6,
                    contractual_due_date=date(2026, 8, 17),
                    effective_due_date=date(2026, 8, 17),
                    contractual_amount=Decimal("200.00"),
                    allocated_amount=Decimal("0.00"),
                    last_adjustment_id=None,
                ),
                NoCollectionInstallmentState(
                    installment_id=12,
                    installment_number=7,
                    contractual_due_date=date(2026, 8, 18),
                    effective_due_date=date(2026, 8, 18),
                    contractual_amount=Decimal("200.00"),
                    allocated_amount=Decimal("0.00"),
                    last_adjustment_id=None,
                ),
            ),
            active_no_collection=(),
        )


def _client() -> tuple[TestClient, FakeQueryRepository]:
    auth = FakeAuthClient()
    accounts = FakeAccounts()
    query = FakeQueryRepository()
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: auth
    app.dependency_overrides[account_repository_dependency] = lambda: accounts
    app.dependency_overrides[management_no_collection_query_repository_dependency] = (
        lambda: query
    )
    return TestClient(app), query


def _headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer management-token",
        "X-Device-Id": "management-device",
    }


def test_management_state_returns_operational_version_and_contract_dates() -> None:
    client, query = _client()

    response = client.get(
        f"/api/mobile/v1/management/no-collection/loans/{LOAN_ID}",
        headers=_headers(),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert query.seen_loan_id == LOAN_ID
    assert data["operational_version"] == 3
    assert data["payment_frequency"] == "daily"
    assert data["semi_monthly_days"] == [15, 30]
    assert data["installments"][0]["contractual_due_date"] == "2026-08-16"
    assert data["installments"][0]["effective_due_date"] == "2026-08-16"
    assert data["installments"][0]["remaining_amount"] == "200.00"


def test_management_preview_returns_exact_old_to_new_schedule_without_writing() -> None:
    client, query = _client()

    response = client.post(
        "/api/mobile/v1/management/no-collection/preview",
        headers=_headers(),
        json={
            "loan_id": str(LOAN_ID),
            "expected_operational_version": 3,
            "no_collection_date": "2026-08-17",
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert query.seen_loan_id == LOAN_ID
    assert data["operational_version"] == 3
    assert data["no_collection_date"] == "2026-08-17"
    assert data["payment_frequency"] == "daily"
    assert data["shifts"] == [
        {
            "installment_id": 11,
            "installment_number": 6,
            "contractual_due_date": "2026-08-17",
            "prior_effective_due_date": "2026-08-17",
            "new_effective_due_date": "2026-08-18",
            "contractual_amount": "200.00",
        },
        {
            "installment_id": 12,
            "installment_number": 7,
            "contractual_due_date": "2026-08-18",
            "prior_effective_due_date": "2026-08-18",
            "new_effective_due_date": "2026-08-19",
            "contractual_amount": "200.00",
        },
    ]


def test_management_preview_rejects_stale_operational_version() -> None:
    client, _ = _client()

    response = client.post(
        "/api/v1/management/no-collection/preview",
        headers=_headers(),
        json={
            "loan_id": str(LOAN_ID),
            "expected_operational_version": 2,
            "no_collection_date": "2026-08-17",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "no_collection_conflict"
