from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.main import create_app
from gilbic_backend.remittance_transfer_journal_api import (
    remittance_transfer_journal_repository_dependency,
)
from gilbic_backend.remittance_transfer_journal_repository import (
    RemittanceTransferJournalStatusRecord,
)


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
MANAGEMENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
REMITTANCE_ID = UUID("33333333-3333-4333-8333-333333333333")
EVIDENCE_ID = UUID("44444444-4444-4444-8444-444444444444")
PREPARATION_ID = UUID("55555555-5555-4555-8555-555555555555")
JOURNAL_ID = UUID("66666666-6666-4666-8666-666666666666")
PERIOD_ID = UUID("77777777-7777-4777-8777-777777777777")
DEBIT_ACCOUNT_ID = UUID("88888888-8888-4888-8888-888888888888")
CREDIT_ACCOUNT_ID = UUID("99999999-9999-4999-8999-999999999999")
POSTING_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
REVERSAL_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
REVERSAL_JOURNAL_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
DRAFT_TOKEN = "a" * 64
POSTING_TOKEN = "b" * 64


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
            permissions=(
                "accounting.view",
                "accounting.remittance_transfer.journal.prepare",
                "accounting.remittance_transfer.journal.post",
                "accounting.remittance_transfer.journal.reverse",
            ),
            device_registered=True,
        )


class FakeRepository:
    def __init__(self) -> None:
        self.prepare_request: dict[str, object] | None = None
        self.post_request: dict[str, object] | None = None
        self.reverse_request: dict[str, object] | None = None
        self.state = "draft"

    def _status(self) -> RemittanceTransferJournalStatusRecord:
        posted = self.state in {"posted", "reversed"}
        reversed_ = self.state == "reversed"
        return RemittanceTransferJournalStatusRecord(
            preparation_id=PREPARATION_ID,
            remittance_id=REMITTANCE_ID,
            transfer_evidence_id=EVIDENCE_ID,
            journal_entry_id=JOURNAL_ID,
            source_event_key=f"remittance_transfer:{REMITTANCE_ID}",
            draft_review_token=DRAFT_TOKEN,
            posting_date=date(2026, 8, 12),
            fiscal_period_id=PERIOD_ID,
            debit_account_id=DEBIT_ACCOUNT_ID,
            debit_account_system_key="cash_office",
            credit_account_id=CREDIT_ACCOUNT_ID,
            credit_account_system_key="cash_collector_custody",
            amount=Decimal("1500.00"),
            journal_status="posted" if posted else "draft",
            entry_number="JE-202608-00000001" if posted else None,
            posting_id=POSTING_ID if posted else None,
            posting_review_token=POSTING_TOKEN if posted else None,
            posted_by_user_id=MANAGEMENT_USER_ID if posted else None,
            posted_at=(
                datetime(2026, 8, 12, 4, 0, tzinfo=timezone.utc)
                if posted
                else None
            ),
            reversal_id=REVERSAL_ID if reversed_ else None,
            reversal_journal_entry_id=REVERSAL_JOURNAL_ID if reversed_ else None,
            reversal_entry_number="JE-202608-00000002" if reversed_ else None,
            reversal_posting_date=date(2026, 8, 12) if reversed_ else None,
            reversal_reason="Correct destination transfer" if reversed_ else None,
            posting_ready=not posted,
            posted_audit_exact=posted,
            reversal_audit_exact=reversed_,
            lifecycle_status=self.state,
            income_recognition=False,
            explicit_management_posting=True,
            automatic_source_posting=False,
        )

    def list_status(self, **kwargs):
        return (self._status(),)

    def prepare(self, **kwargs):
        self.prepare_request = kwargs
        self.state = "draft"
        return self._status()

    def post(self, **kwargs):
        self.post_request = kwargs
        self.state = "posted"
        return self._status()

    def reverse(self, **kwargs):
        self.reverse_request = kwargs
        self.state = "reversed"
        return self._status()


def client_with_fakes() -> tuple[TestClient, FakeRepository]:
    repository = FakeRepository()
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts()
    app.dependency_overrides[remittance_transfer_journal_repository_dependency] = (
        lambda: repository
    )
    return TestClient(app), repository


def headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer management-token",
        "X-Device-Id": "management-device",
    }


def test_status_reports_asset_to_asset_explicit_management_policy() -> None:
    client, _ = client_with_fakes()
    response = client.get(
        "/api/v1/management/accounting/remittance-transfers/journals/status",
        headers=headers(),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["income_recognition"] is False
    assert data["explicit_management_posting"] is True
    assert data["automatic_source_posting"] is False
    row = data["journals"][0]
    assert row["debit_account_system_key"] == "cash_office"
    assert row["credit_account_system_key"] == "cash_collector_custody"
    assert row["posting_ready"] is True


def test_management_can_prepare_exact_reviewed_remittance_transfer_draft() -> None:
    client, repository = client_with_fakes()
    response = client.post(
        "/api/v1/management/accounting/remittance-transfers/journals/prepare",
        headers=headers(),
        json={
            "remittance_id": str(REMITTANCE_ID),
            "review_token": DRAFT_TOKEN,
            "transfer_evidence_id": str(EVIDENCE_ID),
            "source_event_key": f"remittance_transfer:{REMITTANCE_ID}",
            "posting_date": "2026-08-12",
            "debit_account_system_key": "cash_office",
            "credit_account_system_key": "cash_collector_custody",
            "amount": "1500.00",
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["lifecycle_status"] == "draft"
    assert data["amount"] == "1500.00"
    assert data["income_recognition"] is False
    assert repository.prepare_request is not None
    assert repository.prepare_request["actor_user_id"] == MANAGEMENT_USER_ID
    assert repository.prepare_request["remittance_id"] == REMITTANCE_ID


def test_management_can_explicitly_post_protected_remittance_transfer() -> None:
    client, repository = client_with_fakes()
    response = client.post(
        f"/api/v1/management/accounting/remittance-transfers/journals/{PREPARATION_ID}/post",
        headers=headers(),
        json={
            "posting_review_token": POSTING_TOKEN,
            "expected_journal_entry_id": str(JOURNAL_ID),
            "expected_source_event_key": f"remittance_transfer:{REMITTANCE_ID}",
            "expected_draft_review_token": DRAFT_TOKEN,
            "expected_amount": "1500.00",
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["lifecycle_status"] == "posted"
    assert data["posted_audit_exact"] is True
    assert data["automatic_source_posting"] is False
    assert repository.post_request is not None
    assert repository.post_request["preparation_id"] == PREPARATION_ID


def test_management_can_reverse_posted_remittance_transfer() -> None:
    client, repository = client_with_fakes()
    response = client.post(
        f"/api/v1/management/accounting/remittance-transfers/journals/postings/{POSTING_ID}/reverse",
        headers=headers(),
        json={
            "reversal_posting_date": "2026-08-12",
            "reason": "Correct destination transfer",
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["lifecycle_status"] == "reversed"
    assert data["posted_audit_exact"] is True
    assert data["reversal_audit_exact"] is True
    assert data["income_recognition"] is False
    assert repository.reverse_request is not None
    assert repository.reverse_request["posting_id"] == POSTING_ID


def test_prepare_rejects_income_or_collector_custody_as_destination() -> None:
    client, _ = client_with_fakes()
    response = client.post(
        "/api/v1/management/accounting/remittance-transfers/journals/prepare",
        headers=headers(),
        json={
            "remittance_id": str(REMITTANCE_ID),
            "review_token": DRAFT_TOKEN,
            "transfer_evidence_id": str(EVIDENCE_ID),
            "source_event_key": f"remittance_transfer:{REMITTANCE_ID}",
            "posting_date": "2026-08-12",
            "debit_account_system_key": "interest_income_regular",
            "credit_account_system_key": "cash_collector_custody",
            "amount": "1500.00",
        },
    )
    assert response.status_code == 422
