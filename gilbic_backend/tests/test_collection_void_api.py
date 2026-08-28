from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import (
    account_repository_dependency,
    auth_client_dependency,
)
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.collection_void_api import collection_void_repository_dependency
from gilbic_backend.collection_void_repository import (
    CollectionVoidCandidate,
    CollectionVoidLocked,
    CollectionVoidRecord,
)
from gilbic_backend.main import create_app
from gilbic_backend.seven_by_seven_extra_principal_reversal import (
    ExtraPrincipalReversalRequestResult,
)

AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
MANAGEMENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
COLLECTOR_USER_ID = UUID("33333333-3333-4333-8333-333333333333")
CLIENT_ID = UUID("44444444-4444-4444-8444-444444444444")
LOAN_ID = UUID("55555555-5555-4555-8555-555555555555")
TRANSACTION_ID = UUID("66666666-6666-4666-8666-666666666666")
ADJUSTMENT_ID = UUID("77777777-7777-4777-8777-777777777777")
REVERSAL_REQUEST_ID = UUID("88888888-8888-4888-8888-888888888888")
REVERSAL_KEY = UUID("99999999-9999-4999-8999-999999999999")
RECEIPT = "GBC-20260805-00000008"


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
    def __init__(self, *, include_extra_principal_reverse: bool = True) -> None:
        self.include_extra_principal_reverse = include_extra_principal_reverse

    def get_context_for_device(
        self,
        *,
        auth_user_id: UUID,
        device_identifier: str | None,
    ) -> AccountContext:
        assert auth_user_id == AUTH_USER_ID
        assert device_identifier == "management-device"
        permissions = ["collection.void.unremitted"]
        if self.include_extra_principal_reverse:
            permissions.append("lending.extra_principal.reverse")
        return AccountContext(
            user_id=MANAGEMENT_USER_ID,
            auth_user_id=AUTH_USER_ID,
            username="management.one",
            email="management@example.com",
            full_name="Management One",
            status="active",
            roles=("management",),
            permissions=tuple(permissions),
            device_registered=True,
        )


class FakeVoids:
    def __init__(self) -> None:
        self.void_request: dict[str, object] | None = None
        self.error: Exception | None = None
        self.result: (
            CollectionVoidRecord | ExtraPrincipalReversalRequestResult | None
        ) = None

    def find_by_receipt(self, *, receipt_number: str) -> CollectionVoidCandidate:
        if self.error is not None:
            raise self.error
        assert receipt_number == RECEIPT
        return CollectionVoidCandidate(
            transaction_id=TRANSACTION_ID,
            receipt_number=RECEIPT,
            client_id=CLIENT_ID,
            client_code="TEST-REG-001",
            client_name="TEST CLIENT REGULAR",
            loan_id=LOAN_ID,
            loan_type="Regular",
            collector_name="Test Collector",
            collection_date=date(2026, 8, 5),
            entry_type="advance",
            amount=Decimal("50.00"),
            covered_dates=(date(2026, 8, 6),),
            previous_balance=Decimal("4950.00"),
            official_balance=Decimal("4900.00"),
            is_locked=False,
            is_voided=False,
        )

    def void_unremitted(
        self, **kwargs
    ) -> CollectionVoidRecord | ExtraPrincipalReversalRequestResult:
        if self.error is not None:
            raise self.error
        self.void_request = kwargs
        if self.result is not None:
            return self.result
        return CollectionVoidRecord(
            transaction_id=TRANSACTION_ID,
            receipt_number=RECEIPT,
            client_id=CLIENT_ID,
            client_code="TEST-REG-001",
            client_name="TEST CLIENT REGULAR",
            loan_id=LOAN_ID,
            collector_user_id=COLLECTOR_USER_ID,
            collector_name="Test Collector",
            collection_date=date(2026, 8, 5),
            entry_type="advance",
            amount=Decimal("50.00"),
            covered_dates=(date(2026, 8, 6),),
            restored_balance=Decimal("4950.00"),
            state_version=3,
            reason="Payment posted to the wrong borrower",
            voided_at=datetime(2026, 8, 5, 7, 40, tzinfo=UTC),
        )


def client_with_fakes(
    *, accounts: FakeAccounts | None = None
) -> tuple[TestClient, FakeVoids]:
    voids = FakeVoids()
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = (
        lambda: accounts or FakeAccounts()
    )
    app.dependency_overrides[collection_void_repository_dependency] = lambda: voids
    return TestClient(app), voids


def headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer management-token",
        "X-Device-Id": "management-device",
    }


def test_management_can_find_unremitted_receipt() -> None:
    client, _ = client_with_fakes()

    response = client.get(
        f"/api/mobile/v1/management/collections/by-receipt/{RECEIPT}",
        headers=headers(),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["transaction_id"] == str(TRANSACTION_ID)
    assert data["client_name"] == "TEST CLIENT REGULAR"
    assert data["amount"] == "50.00"
    assert data["covered_dates"] == ["2026-08-06"]
    assert data["official_balance"] == "4900.00"


def test_management_can_void_latest_unremitted_collection() -> None:
    client, voids = client_with_fakes()

    response = client.post(
        f"/api/v1/management/collections/{TRANSACTION_ID}/void",
        headers=headers(),
        json={"reason": "Payment posted to the wrong borrower"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["receipt_number"] == RECEIPT
    assert data["restored_balance"] == "4950.00"
    assert data["state_version"] == 3
    assert voids.void_request is not None
    assert voids.void_request["actor_user_id"] == MANAGEMENT_USER_ID
    assert voids.void_request["transaction_id"] == TRANSACTION_ID
    assert voids.void_request["idempotency_key"] is None


def test_extra_principal_void_forwards_idempotency_key() -> None:
    client, voids = client_with_fakes()

    response = client.post(
        f"/api/v1/management/collections/{TRANSACTION_ID}/void",
        headers=headers(),
        json={
            "reason": "Payment posted to the wrong borrower",
            "idempotency_key": str(REVERSAL_KEY),
        },
    )

    assert response.status_code == 200
    assert voids.void_request is not None
    assert voids.void_request["idempotency_key"] == REVERSAL_KEY


def test_extra_principal_void_requires_dedicated_permission() -> None:
    client, voids = client_with_fakes(
        accounts=FakeAccounts(include_extra_principal_reverse=False)
    )

    response = client.post(
        f"/api/v1/management/collections/{TRANSACTION_ID}/void",
        headers=headers(),
        json={"reason": "Wrong receipt", "idempotency_key": str(REVERSAL_KEY)},
    )

    assert response.status_code == 403
    assert voids.void_request is None


def test_released_refund_returns_stable_blocked_reversal_result() -> None:
    client, voids = client_with_fakes()
    voids.result = ExtraPrincipalReversalRequestResult(
        request_id=REVERSAL_REQUEST_ID,
        adjustment_id=ADJUSTMENT_ID,
        transaction_id=TRANSACTION_ID,
        outcome="blocked_refund_released",
        released_refund_amount=Decimal("25.00"),
        result_payload={
            "request_id": str(REVERSAL_REQUEST_ID),
            "adjustment_id": str(ADJUSTMENT_ID),
            "transaction_id": str(TRANSACTION_ID),
            "outcome": "blocked_refund_released",
            "released_refund_amount": "25.00",
            "code": "seven_by_seven_extra_principal_reversal_refund_released",
            "message": "Physical Refund Due cash was already released.",
        },
        collection_void=None,
    )

    first = client.post(
        f"/api/v1/management/collections/{TRANSACTION_ID}/void",
        headers=headers(),
        json={"reason": "Wrong receipt", "idempotency_key": str(REVERSAL_KEY)},
    )
    second = client.post(
        f"/api/v1/management/collections/{TRANSACTION_ID}/void",
        headers=headers(),
        json={"reason": "Wrong receipt", "idempotency_key": str(REVERSAL_KEY)},
    )

    assert first.status_code == second.status_code == 409
    assert first.json() == second.json()
    assert first.json()["detail"]["code"] == (
        "seven_by_seven_extra_principal_reversal_refund_released"
    )


def test_remitted_collection_void_returns_conflict() -> None:
    client, voids = client_with_fakes()
    voids.error = CollectionVoidLocked(
        "This collection is already included in a remittance and cannot be voided."
    )

    response = client.post(
        f"/api/v1/management/collections/{TRANSACTION_ID}/void",
        headers=headers(),
        json={"reason": "Wrong borrower"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "collection_void_locked"
