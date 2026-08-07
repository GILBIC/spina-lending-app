from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.general_journal_api import general_journal_repository_dependency
from gilbic_backend.general_journal_repository import (
    JournalEntry,
    JournalLine,
    TrialBalance,
    TrialBalanceLine,
)
from gilbic_backend.main import create_app


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
MANAGEMENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
ENTRY_ID = UUID("33333333-3333-4333-8333-333333333333")
PERIOD_ID = UUID("44444444-4444-4444-8444-444444444444")


class FakeAuthClient:
    def get_user(self, *, access_token: str) -> AuthSession:
        return AuthSession(
            auth_user_id=AUTH_USER_ID,
            email="manager@example.com",
            access_token=access_token,
            refresh_token=None,
            expires_at=None,
            email_confirmed=True,
        )


class FakeAccounts:
    def __init__(self, *, role: str = "management", can_manage: bool = True) -> None:
        self.role = role
        self.can_manage = can_manage

    def get_context_for_device(
        self,
        *,
        auth_user_id: UUID,
        device_identifier: str | None,
    ) -> AccountContext:
        permissions = ["accounting.view"]
        if self.can_manage:
            permissions.append("accounting.journal.manage")
        return AccountContext(
            user_id=MANAGEMENT_USER_ID,
            auth_user_id=auth_user_id,
            username="manager",
            email="manager@example.com",
            full_name="Management User",
            status="active",
            roles=(self.role,),
            permissions=tuple(permissions),
            device_registered=True,
        )


class FakeJournalRepository:
    def __init__(self) -> None:
        self.created = False
        self.posted = False

    def list_journals(self, *, limit: int = 100):
        return (self._entry(status="posted" if self.posted else "draft"),)

    def create_manual_draft(self, **kwargs):
        self.created = True
        assert kwargs["actor_user_id"] == MANAGEMENT_USER_ID
        assert kwargs["posting_date"] == date(2026, 8, 8)
        assert kwargs["lines"][0]["account_code"] == "1010"
        return self._entry(status="draft")

    def update_manual_draft(self, **kwargs):
        return self._entry(status="draft")

    def cancel_manual_draft(self, **kwargs):
        return None

    def post_journal(self, **kwargs):
        self.posted = True
        return self._entry(status="posted")

    def create_reversal_draft(self, **kwargs):
        return self._entry(status="draft", reversal=True)

    def trial_balance(self, *, period_id=None):
        return TrialBalance(
            period_id=period_id,
            period_label="August 2026" if period_id else None,
            total_debits=Decimal("100.00"),
            total_credits=Decimal("100.00"),
            balanced=True,
            lines=(
                TrialBalanceLine(
                    account_code="1010",
                    account_name="Cash - Office",
                    account_type="asset",
                    normal_balance="debit",
                    total_debit=Decimal("100.00"),
                    total_credit=Decimal("0.00"),
                    debit_balance=Decimal("100.00"),
                    credit_balance=Decimal("0.00"),
                ),
                TrialBalanceLine(
                    account_code="3000",
                    account_name="Capital",
                    account_type="equity",
                    normal_balance="credit",
                    total_debit=Decimal("0.00"),
                    total_credit=Decimal("100.00"),
                    debit_balance=Decimal("0.00"),
                    credit_balance=Decimal("100.00"),
                ),
            ),
        )

    @staticmethod
    def _entry(*, status: str, reversal: bool = False) -> JournalEntry:
        now = datetime(2026, 8, 8, 1, 0, tzinfo=timezone.utc)
        return JournalEntry(
            entry_id=ENTRY_ID,
            entry_number="JE-202608-00000001" if status == "posted" else None,
            period_id=PERIOD_ID,
            period_label="August 2026",
            posting_date=date(2026, 8, 8),
            description="Test manual journal",
            status=status,
            source_type="reversal" if reversal else "manual",
            source_reference=None,
            reversal_of_entry_id=ENTRY_ID if reversal else None,
            created_by_name="Management User",
            posted_by_name="Management User" if status == "posted" else None,
            created_at=now,
            posted_at=now if status == "posted" else None,
            total_debit=Decimal("100.00"),
            total_credit=Decimal("100.00"),
            lines=(
                JournalLine(
                    line_number=1,
                    account_code="1010",
                    account_name="Cash - Office",
                    description="",
                    debit=Decimal("100.00"),
                    credit=Decimal("0.00"),
                ),
                JournalLine(
                    line_number=2,
                    account_code="3000",
                    account_name="Capital",
                    description="",
                    debit=Decimal("0.00"),
                    credit=Decimal("100.00"),
                ),
            ),
        )


def headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Device-Id": "test-device",
    }


def client_with_fakes(*, role: str = "management", can_manage: bool = True):
    app = create_app()
    fake = FakeJournalRepository()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts(
        role=role,
        can_manage=can_manage,
    )
    app.dependency_overrides[general_journal_repository_dependency] = lambda: fake
    return TestClient(app), fake


def test_management_can_view_general_journal_and_trial_balance() -> None:
    client, _ = client_with_fakes()

    response = client.get(
        "/api/mobile/v1/management/financial-accounting/journals",
        headers=headers(),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["can_manage"] is True
    assert data["automatic_loan_posting_enabled"] is False
    assert data["entries"][0]["total_debit"] == "100.00"

    trial = client.get(
        "/api/mobile/v1/management/financial-accounting/trial-balance",
        headers=headers(),
    )
    assert trial.status_code == 200
    trial_data = trial.json()["data"]["trial_balance"]
    assert trial_data["balanced"] is True
    assert trial_data["total_debits"] == "100.00"
    assert trial_data["total_credits"] == "100.00"


def test_management_can_create_balanced_manual_draft() -> None:
    client, fake = client_with_fakes()
    response = client.post(
        "/api/mobile/v1/management/financial-accounting/journals",
        headers=headers(),
        json={
            "posting_date": "2026-08-08",
            "description": "Test manual journal",
            "lines": [
                {"account_code": "1010", "debit": "100.00", "credit": "0.00"},
                {"account_code": "3000", "debit": "0.00", "credit": "100.00"},
            ],
        },
    )
    assert response.status_code == 201
    assert fake.created is True
    assert response.json()["data"]["entry"]["status"] == "draft"


def test_unbalanced_manual_journal_is_rejected_before_repository() -> None:
    client, fake = client_with_fakes()
    response = client.post(
        "/api/mobile/v1/management/financial-accounting/journals",
        headers=headers(),
        json={
            "posting_date": "2026-08-08",
            "description": "Unbalanced test",
            "lines": [
                {"account_code": "1010", "debit": "100.00", "credit": "0.00"},
                {"account_code": "3000", "debit": "0.00", "credit": "90.00"},
            ],
        },
    )
    assert response.status_code == 422
    assert fake.created is False


def test_post_requires_explicit_confirmation() -> None:
    client, fake = client_with_fakes()
    response = client.post(
        f"/api/mobile/v1/management/financial-accounting/journals/{ENTRY_ID}/post",
        headers=headers(),
        json={"confirm": False},
    )
    assert response.status_code == 409
    assert fake.posted is False

    confirmed = client.post(
        f"/api/mobile/v1/management/financial-accounting/journals/{ENTRY_ID}/post",
        headers=headers(),
        json={"confirm": True},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["data"]["entry"]["entry_number"] == "JE-202608-00000001"
    assert fake.posted is True


def test_non_management_role_is_denied() -> None:
    client, _ = client_with_fakes(role="client")
    response = client.get(
        "/api/mobile/v1/management/financial-accounting/journals",
        headers=headers(),
    )
    assert response.status_code == 403
