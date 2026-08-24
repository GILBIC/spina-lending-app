from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.main import create_app
import gilbic_backend.collector_cash_accountability_api as cash_api


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
COLLECTOR_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
OTHER_COLLECTOR_A = UUID("33333333-3333-4333-8333-333333333333")
OTHER_COLLECTOR_B = UUID("44444444-4444-4444-8444-444444444444")


class FakeAuthClient:
    def get_user(self, *, access_token: str) -> AuthSession:
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
        assert device_identifier == "collector-phone"
        return AccountContext(
            user_id=COLLECTOR_USER_ID,
            auth_user_id=AUTH_USER_ID,
            username="collector.one",
            email="collector@example.com",
            full_name="Collector One",
            status="active",
            roles=("collector",),
            permissions=("remittance.view", "remittance.create"),
            device_registered=True,
        )


class FakeCursor:
    def __init__(self) -> None:
        self.params = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, query, params) -> None:
        assert "collection_transactions" in query
        assert "collection_remittances" in query
        assert "other_by_collector" in query
        self.params = params

    def fetchone(self):
        assert self.params == (COLLECTOR_USER_ID,)
        return {
            "ready_to_remit_amount": Decimal("1250.00"),
            "ready_to_remit_count": 6,
            "awaiting_acceptance_amount": Decimal("500.00"),
            "awaiting_acceptance_count": 2,
            "assigned_area_cash_held": Decimal("1100.00"),
            "other_area_cash_held": Decimal("650.00"),
            "other_area_by_collector": [
                {
                    "collector_user_id": str(OTHER_COLLECTOR_A),
                    "collector_name": "Collector Two",
                    "amount": 400.0,
                },
                {
                    "collector_user_id": str(OTHER_COLLECTOR_B),
                    "collector_name": "Collector Three",
                    "amount": 250.0,
                },
            ],
        }


class FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def cursor(self, *, row_factory=None):
        return FakeCursor()


@contextmanager
def fake_open_connection():
    yield FakeConnection()


def test_cash_accountability_includes_unsubmitted_and_submitted_cash(monkeypatch) -> None:
    monkeypatch.setattr(cash_api, "open_connection", fake_open_connection)
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts()
    client = TestClient(app)

    response = client.get(
        "/api/mobile/v1/collector/cash-accountability",
        headers={
            "Authorization": "Bearer session-token",
            "X-Device-Id": "collector-phone",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"] == {
        "total_cash_held": "1750.00",
        "assigned_area_cash_held": "1100.00",
        "other_area_cash_held": "650.00",
        "other_area_by_collector": [
            {
                "collector_user_id": str(OTHER_COLLECTOR_A),
                "collector_name": "Collector Two",
                "amount": "400.00",
            },
            {
                "collector_user_id": str(OTHER_COLLECTOR_B),
                "collector_name": "Collector Three",
                "amount": "250.00",
            },
        ],
        "ready_to_remit_amount": "1250.00",
        "ready_to_remit_count": 6,
        "awaiting_acceptance_amount": "500.00",
        "awaiting_acceptance_count": 2,
    }
