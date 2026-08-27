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
    management_no_collection_repository_dependency,
)
from gilbic_backend.management_no_collection_repository import (
    NoCollectionAdjustmentRecord,
    NoCollectionShiftRecord,
)


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
MANAGEMENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
LOAN_ID = UUID("33333333-3333-4333-8333-333333333333")
SCHEDULE_ID = UUID("44444444-4444-4444-8444-444444444444")
ADJUSTMENT_ID = UUID("55555555-5555-4555-8555-555555555555")
REVERSAL_ID = UUID("66666666-6666-4666-8666-666666666666")


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
    def __init__(self) -> None:
        self.context = AccountContext(
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

    def get_context_for_device(
        self,
        *,
        auth_user_id: UUID,
        device_identifier: str | None,
    ) -> AccountContext:
        assert auth_user_id == AUTH_USER_ID
        assert device_identifier == "management-device"
        return self.context


class FakeNoCollectionRepository:
    def __init__(self) -> None:
        self.declaration_request = None
        self.reversal_request = None

    def declare_many(self, **kwargs):
        self.declaration_request = kwargs
        return (_record(adjustment_id=ADJUSTMENT_ID),)

    def reverse(self, **kwargs):
        self.reversal_request = kwargs
        return _record(
            adjustment_id=REVERSAL_ID,
            adjustment_type="reversal",
            expected_version=1,
            resulting_version=2,
            reverses=ADJUSTMENT_ID,
        )


def _record(
    *,
    adjustment_id: UUID,
    adjustment_type: str = "no_collection",
    expected_version: int = 0,
    resulting_version: int = 1,
    reverses: UUID | None = None,
) -> NoCollectionAdjustmentRecord:
    return NoCollectionAdjustmentRecord(
        adjustment_id=adjustment_id,
        loan_id=LOAN_ID,
        schedule_id=SCHEDULE_ID,
        schedule_version=1,
        payment_frequency="daily",
        no_collection_date=date(2026, 8, 16),
        reason="Office closed due to declared no-collection day",
        adjustment_type=adjustment_type,
        expected_operational_version=expected_version,
        resulting_operational_version=resulting_version,
        reverses_adjustment_id=reverses,
        created_at=datetime(2026, 8, 16, 1, 30, tzinfo=timezone.utc),
        shifts=(
            NoCollectionShiftRecord(
                installment_id=10,
                installment_number=5,
                contractual_due_date=date(2026, 8, 16),
                prior_effective_due_date=date(2026, 8, 16),
                new_effective_due_date=date(2026, 8, 17),
                contractual_amount=Decimal("200.00"),
            ),
        ),
    )


def _client():
    auth = FakeAuthClient()
    accounts = FakeAccounts()
    repository = FakeNoCollectionRepository()
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: auth
    app.dependency_overrides[account_repository_dependency] = lambda: accounts
    app.dependency_overrides[management_no_collection_repository_dependency] = (
        lambda: repository
    )
    return TestClient(app), accounts, repository


def _headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer management-token",
        "X-Device-Id": "management-device",
    }


def test_management_can_declare_per_loan_no_collection() -> None:
    client, _, repository = _client()

    response = client.post(
        "/api/mobile/v1/management/no-collection",
        headers=_headers(),
        json={
            "no_collection_date": "2026-08-16",
            "reason": "Office closed due to declared no-collection day",
            "loans": [
                {
                    "loan_id": str(LOAN_ID),
                    "expected_operational_version": 0,
                }
            ],
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["no_collection_date"] == "2026-08-16"
    assert data["loans"][0]["adjustment_type"] == "no_collection"
    assert data["loans"][0]["resulting_operational_version"] == 1
    assert data["loans"][0]["shifts"] == [
        {
            "installment_id": 10,
            "installment_number": 5,
            "contractual_due_date": "2026-08-16",
            "prior_effective_due_date": "2026-08-16",
            "new_effective_due_date": "2026-08-17",
            "contractual_amount": "200.00",
        }
    ]
    assert repository.declaration_request is not None
    selection = repository.declaration_request["selections"][0]
    assert selection.loan_id == LOAN_ID
    assert selection.expected_operational_version == 0


def test_management_can_reverse_latest_safe_no_collection_adjustment() -> None:
    client, _, repository = _client()

    response = client.post(
        f"/api/mobile/v1/management/no-collection/{ADJUSTMENT_ID}/reverse",
        headers=_headers(),
        json={
            "expected_operational_version": 1,
            "reason": "Management restored the original collection day",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["adjustment_type"] == "reversal"
    assert response.json()["data"]["reverses_adjustment_id"] == str(ADJUSTMENT_ID)
    assert repository.reversal_request["adjustment_id"] == ADJUSTMENT_ID
    assert repository.reversal_request["expected_operational_version"] == 1


def test_non_management_role_is_rejected_even_if_permission_is_present() -> None:
    client, accounts, repository = _client()
    accounts.context = AccountContext(
        user_id=MANAGEMENT_USER_ID,
        auth_user_id=AUTH_USER_ID,
        username="collector.one",
        email="collector@example.com",
        full_name="Collector One",
        status="active",
        roles=("collector",),
        permissions=("lending.no_collection.manage",),
        device_registered=True,
    )

    response = client.post(
        "/api/v1/management/no-collection",
        headers=_headers(),
        json={
            "no_collection_date": "2026-08-16",
            "reason": "Attempt",
            "loans": [
                {
                    "loan_id": str(LOAN_ID),
                    "expected_operational_version": 0,
                }
            ],
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "management_role_required"
    assert repository.declaration_request is None
