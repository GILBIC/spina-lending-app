from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.collection_correction_api import correction_repository_dependency
from gilbic_backend.collection_correction_repository import (
    CollectionCorrectionLocked,
    CollectionCorrectionRecord,
)
from gilbic_backend.main import create_app


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
COLLECTOR_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
CLIENT_ID = UUID("33333333-3333-4333-8333-333333333333")
LOAN_ID = UUID("44444444-4444-4444-8444-444444444444")
TRANSACTION_ID = UUID("55555555-5555-4555-8555-555555555555")


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


class FakeCorrections:
    def __init__(self) -> None:
        self.request: dict[str, object] | None = None
        self.error: Exception | None = None

    def correct_own_unremitted(self, **kwargs) -> CollectionCorrectionRecord:
        if self.error is not None:
            raise self.error
        self.request = kwargs
        return CollectionCorrectionRecord(
            transaction_id=TRANSACTION_ID,
            client_id=CLIENT_ID,
            loan_id=LOAN_ID,
            collection_date=date(2026, 8, 2),
            entry_type="advance",
            amount=Decimal("100.00"),
            covered_dates=(date(2026, 8, 2), date(2026, 8, 4)),
            note="Correct selected dates",
            official_balance=Decimal("4900.00"),
            pass_count_after=0,
            receipt_number="GBC-20260802-00000001",
            edit_version=1,
            route_revision=f"loan:{LOAN_ID}:v2",
            edited_at=datetime(2026, 8, 2, 8, tzinfo=timezone.utc),
        )


def client_with_fakes() -> tuple[TestClient, FakeCorrections]:
    corrections = FakeCorrections()
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts()
    app.dependency_overrides[correction_repository_dependency] = lambda: corrections
    return TestClient(app), corrections


def headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer collector-token",
        "X-Device-Id": "device-one",
    }


def test_original_collector_can_correct_exact_unremitted_dates() -> None:
    client, corrections = client_with_fakes()

    response = client.patch(
        f"/api/mobile/v1/collector/collections/{TRANSACTION_ID}",
        headers=headers(),
        json={
            "entry_type": "advance",
            "amount": "100.00",
            "covered_dates": ["2026-08-02", "2026-08-04"],
            "note": "Correct selected dates",
            "reason": "Wrong date tapped",
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["transaction_id"] == str(TRANSACTION_ID)
    assert data["covered_dates"] == ["2026-08-02", "2026-08-04"]
    assert data["official_balance"] == "4900.00"
    assert data["edit_version"] == 1
    assert corrections.request is not None
    assert corrections.request["actor_user_id"] == COLLECTOR_USER_ID
    assert corrections.request["reason"] == "Wrong date tapped"


def test_remitted_collection_correction_returns_conflict() -> None:
    client, corrections = client_with_fakes()
    corrections.error = CollectionCorrectionLocked(
        "This entry is already included in a remittance and cannot be edited."
    )

    response = client.patch(
        f"/api/v1/collector/collections/{TRANSACTION_ID}",
        headers=headers(),
        json={
            "entry_type": "payment",
            "amount": "50.00",
            "covered_dates": ["2026-08-02"],
            "note": "",
            "reason": "Wrong amount",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "collection_correction_locked"
