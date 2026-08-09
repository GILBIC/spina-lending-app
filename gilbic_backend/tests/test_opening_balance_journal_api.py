from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.main import create_app
from gilbic_backend.opening_balance_journal_api import (
    opening_balance_journal_repository_dependency,
)
from gilbic_backend.opening_balance_journal_repository import (
    OpeningBalanceJournalPreparation,
)


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
MANAGEMENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
WORKBOOK_ID = UUID("33333333-3333-4333-8333-333333333333")
JOURNAL_ID = UUID("44444444-4444-4444-8444-444444444444")


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
    def __init__(self, *, role: str = "management", can_prepare: bool = True) -> None:
        self.role = role
        self.can_prepare = can_prepare

    def get_context_for_device(
        self,
        *,
        auth_user_id: UUID,
        device_identifier: str | None,
    ) -> AccountContext:
        permissions = ["accounting.view"]
        if self.can_prepare:
            permissions.append("accounting.opening_balance.prepare")
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


class FakeOpeningBalanceJournalRepository:
    def __init__(self) -> None:
        self.prepared = False
        self.actor_user_id: UUID | None = None

    def load_status(self, *, workbook_id: UUID):
        assert workbook_id == WORKBOOK_ID
        return self._item()

    def prepare_draft(self, *, actor_user_id: UUID, workbook_id: UUID):
        assert workbook_id == WORKBOOK_ID
        self.prepared = True
        self.actor_user_id = actor_user_id
        return self._item()

    def _item(self) -> OpeningBalanceJournalPreparation:
        now = datetime(2026, 8, 9, 6, 0, tzinfo=timezone.utc)
        return OpeningBalanceJournalPreparation(
            workbook_id=WORKBOOK_ID,
            cutover_date=date(2026, 8, 8),
            workbook_status="review_ready",
            journal_entry_id=JOURNAL_ID if self.prepared else None,
            journal_status="draft" if self.prepared else None,
            entry_number=None,
            journal_created_at=now if self.prepared else None,
            prepared_by_user_id=MANAGEMENT_USER_ID if self.prepared else None,
            prepared_at=now if self.prepared else None,
            journal_line_count=4 if self.prepared else 0,
            total_debit=Decimal("29343.11") if self.prepared else Decimal("0"),
            total_credit=Decimal("29343.11") if self.prepared else Decimal("0"),
            draft_prepared=self.prepared,
            opening_balance_posting_enabled=False,
            automatic_source_posting_enabled=False,
        )


def headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Device-Id": "test-device",
    }


def client_with_fakes(*, role: str = "management", can_prepare: bool = True):
    app = create_app()
    fake = FakeOpeningBalanceJournalRepository()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts(
        role=role,
        can_prepare=can_prepare,
    )
    app.dependency_overrides[opening_balance_journal_repository_dependency] = lambda: fake
    return TestClient(app), fake


def test_management_can_view_opening_balance_journal_preparation_status() -> None:
    client, _ = client_with_fakes()
    response = client.get(
        f"/api/mobile/v1/management/financial-accounting/opening-balance-workbook/{WORKBOOK_ID}/journal-draft",
        headers=headers(),
    )

    assert response.status_code == 200
    item = response.json()["data"]["journal_draft"]
    assert item["draft_prepared"] is False
    assert item["opening_balance_posting_enabled"] is False
    assert item["automatic_source_posting_enabled"] is False


def test_preparation_requires_explicit_confirmation() -> None:
    client, fake = client_with_fakes()
    response = client.post(
        f"/api/mobile/v1/management/financial-accounting/opening-balance-workbook/{WORKBOOK_ID}/journal-draft",
        headers=headers(),
        json={"confirm": False},
    )

    assert response.status_code == 409
    assert fake.prepared is False
    assert response.json()["detail"]["code"] == (
        "opening_balance_journal_confirmation_required"
    )


def test_authorized_management_can_prepare_draft_without_posting() -> None:
    client, fake = client_with_fakes()
    response = client.post(
        f"/api/mobile/v1/management/financial-accounting/opening-balance-workbook/{WORKBOOK_ID}/journal-draft",
        headers=headers(),
        json={"confirm": True},
    )

    assert response.status_code == 201
    assert fake.prepared is True
    assert fake.actor_user_id == MANAGEMENT_USER_ID
    item = response.json()["data"]["journal_draft"]
    assert item["journal_entry_id"] == str(JOURNAL_ID)
    assert item["journal_status"] == "draft"
    assert item["entry_number"] is None
    assert item["opening_balance_posting_enabled"] is False


def test_prepare_requires_specific_permission() -> None:
    client, fake = client_with_fakes(can_prepare=False)
    response = client.post(
        f"/api/mobile/v1/management/financial-accounting/opening-balance-workbook/{WORKBOOK_ID}/journal-draft",
        headers=headers(),
        json={"confirm": True},
    )

    assert response.status_code == 403
    assert fake.prepared is False


def test_opening_balance_journal_requires_management_role() -> None:
    client, _ = client_with_fakes(role="collector")
    response = client.get(
        f"/api/mobile/v1/management/financial-accounting/opening-balance-workbook/{WORKBOOK_ID}/journal-draft",
        headers=headers(),
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "management_role_required"
