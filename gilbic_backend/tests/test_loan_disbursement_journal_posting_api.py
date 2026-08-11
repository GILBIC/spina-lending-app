from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.loan_disbursement_journal_posting_api import (
    loan_disbursement_journal_posting_repository_dependency,
)
from gilbic_backend.loan_disbursement_journal_posting_repository import (
    LoanDisbursementJournalPostingStatus,
)
from gilbic_backend.main import create_app


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
MANAGEMENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
EVENT_ID = UUID("33333333-3333-4333-8333-333333333333")
LOAN_ID = UUID("44444444-4444-4444-8444-444444444444")
CLIENT_ID = UUID("55555555-5555-4555-8555-555555555555")
PERIOD_ID = UUID("66666666-6666-4666-8666-666666666666")
DEBIT_ID = UUID("77777777-7777-4777-8777-777777777777")
CREDIT_ID = UUID("88888888-8888-4888-8888-888888888888")
PREPARATION_ID = UUID("99999999-9999-4999-8999-999999999999")
JOURNAL_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
POSTING_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
DRAFT_TOKEN = "c" * 64
POSTING_TOKEN = "d" * 64
SOURCE_KEY = f"loan_disbursement:{EVENT_ID}"


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
    def __init__(
        self,
        *,
        role: str = "management",
        permissions: tuple[str, ...] = (
            "accounting.view",
            "accounting.loan_disbursement.journal.post",
        ),
    ) -> None:
        self.role = role
        self.permissions = permissions

    def get_context_for_device(
        self,
        *,
        auth_user_id: UUID,
        device_identifier: str | None,
    ) -> AccountContext:
        return AccountContext(
            user_id=MANAGEMENT_USER_ID,
            auth_user_id=auth_user_id,
            username="manager",
            email="manager@example.com",
            full_name="Management User",
            status="active",
            roles=(self.role,),
            permissions=self.permissions,
            device_registered=True,
        )


def _status(*, posted: bool = False) -> LoanDisbursementJournalPostingStatus:
    return LoanDisbursementJournalPostingStatus(
        preparation_id=PREPARATION_ID,
        disbursement_event_id=EVENT_ID,
        loan_id=LOAN_ID,
        client_id=CLIENT_ID,
        journal_entry_id=JOURNAL_ID,
        source_event_key=SOURCE_KEY,
        draft_review_token=DRAFT_TOKEN,
        draft_policy_version="new_loan_disbursement_journal_draft_v1",
        posting_date=date(2026, 8, 11),
        fiscal_period_id=PERIOD_ID,
        fiscal_period_label="August 2026",
        fiscal_period_status="open",
        amount=Decimal("5000.00"),
        debit_account_id=DEBIT_ID,
        debit_account_system_key="loans_receivable_regular",
        credit_account_id=CREDIT_ID,
        credit_account_system_key="cash_office",
        line_count=2,
        total_debit=Decimal("5000.00"),
        total_credit=Decimal("5000.00"),
        journal_status="posted" if posted else "draft",
        entry_number="JE-202608-00000001" if posted else None,
        posting_id=POSTING_ID if posted else None,
        posting_review_token=POSTING_TOKEN,
        posting_policy_version="new_loan_disbursement_journal_posting_v1",
        posted_by_user_id=MANAGEMENT_USER_ID if posted else None,
        posted_at=(
            datetime(2026, 8, 11, 13, 0, tzinfo=timezone.utc)
            if posted
            else None
        ),
        posting_ready=not posted,
        posted_audit_exact=posted,
        protected_posting_enabled=True,
        automatic_source_posting_enabled=False,
    )


class FakeRepository:
    def __init__(self, *, posted: bool = False) -> None:
        self.posted = posted
        self.load_calls: list[UUID] = []
        self.post_calls: list[tuple[UUID, UUID, str]] = []

    def load_status(self, *, disbursement_event_id: UUID):
        self.load_calls.append(disbursement_event_id)
        return _status(posted=self.posted)

    def post(
        self,
        *,
        actor_user_id: UUID,
        disbursement_event_id: UUID,
        expected_posting_review_token: str,
    ):
        self.post_calls.append(
            (actor_user_id, disbursement_event_id, expected_posting_review_token)
        )
        self.posted = True
        return _status(posted=True)


def _headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Device-Id": "management-device",
    }


def _confirmation(**overrides):
    payload = {
        "confirm": True,
        "posting_review_token": POSTING_TOKEN,
        "preparation_id": str(PREPARATION_ID),
        "journal_entry_id": str(JOURNAL_ID),
        "source_event_key": SOURCE_KEY,
        "draft_review_token": DRAFT_TOKEN,
        "posting_date": "2026-08-11",
        "amount": "5000.00",
        "debit_account_system_key": "loans_receivable_regular",
        "credit_account_system_key": "cash_office",
        "total_debit": "5000.00",
        "total_credit": "5000.00",
    }
    payload.update(overrides)
    return payload


def _client(
    *,
    role: str = "management",
    permissions: tuple[str, ...] = (
        "accounting.view",
        "accounting.loan_disbursement.journal.post",
    ),
    posted: bool = False,
):
    repository = FakeRepository(posted=posted)
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts(
        role=role,
        permissions=permissions,
    )
    app.dependency_overrides[loan_disbursement_journal_posting_repository_dependency] = (
        lambda: repository
    )
    return TestClient(app), repository


def test_management_posting_review_exposes_exact_confirmation_and_auto_off() -> None:
    client, repository = _client()
    response = client.get(
        f"/api/v1/management/accounting/loan-disbursements/{EVENT_ID}/journal-posting",
        headers=_headers(),
    )
    assert response.status_code == 200
    assert repository.load_calls == [EVENT_ID]
    data = response.json()["data"]["loan_disbursement_journal_posting"]
    assert data["posting_review_token"] == POSTING_TOKEN
    assert data["preparation_id"] == str(PREPARATION_ID)
    assert data["journal_entry_id"] == str(JOURNAL_ID)
    assert data["source_event_key"] == SOURCE_KEY
    assert data["debit_account_system_key"] == "loans_receivable_regular"
    assert data["credit_account_system_key"] == "cash_office"
    assert data["total_debit"] == "5000.00"
    assert data["total_credit"] == "5000.00"
    assert data["posting_ready"] is True
    assert data["posted"] is False
    assert data["automatic_source_posting_enabled"] is False


def test_exact_management_confirmation_posts_once() -> None:
    client, repository = _client()
    response = client.post(
        f"/api/mobile/v1/management/accounting/loan-disbursements/{EVENT_ID}/journal-posting",
        headers=_headers(),
        json=_confirmation(),
    )
    assert response.status_code == 200
    assert repository.post_calls == [(MANAGEMENT_USER_ID, EVENT_ID, POSTING_TOKEN)]
    data = response.json()["data"]["loan_disbursement_journal_posting"]
    assert data["journal_status"] == "posted"
    assert data["entry_number"] == "JE-202608-00000001"
    assert data["posted"] is True
    assert data["posted_audit_exact"] is True
    assert data["automatic_source_posting_enabled"] is False


def test_post_requires_explicit_confirmation_and_every_exact_field() -> None:
    client, repository = _client()
    response = client.post(
        f"/api/v1/management/accounting/loan-disbursements/{EVENT_ID}/journal-posting",
        headers=_headers(),
        json=_confirmation(confirm=False),
    )
    assert response.status_code == 409
    assert repository.post_calls == []

    for override in (
        {"amount": "4999.00"},
        {"credit_account_system_key": "cash_bank_gcash"},
        {"total_credit": "4999.00"},
        {"journal_entry_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaab"},
        {"posting_review_token": "e" * 64},
    ):
        response = client.post(
            f"/api/v1/management/accounting/loan-disbursements/{EVENT_ID}/journal-posting",
            headers=_headers(),
            json=_confirmation(**override),
        )
        assert response.status_code == 409
    assert repository.post_calls == []


def test_exact_retry_is_allowed_when_already_posted_and_audit_exact() -> None:
    client, repository = _client(posted=True)
    response = client.post(
        f"/api/v1/management/accounting/loan-disbursements/{EVENT_ID}/journal-posting",
        headers=_headers(),
        json=_confirmation(),
    )
    assert response.status_code == 200
    assert repository.post_calls == [(MANAGEMENT_USER_ID, EVENT_ID, POSTING_TOKEN)]
    assert response.json()["data"]["loan_disbursement_journal_posting"]["posted"] is True


def test_post_requires_dedicated_management_permission() -> None:
    client, repository = _client(permissions=("accounting.view",))
    response = client.post(
        f"/api/v1/management/accounting/loan-disbursements/{EVENT_ID}/journal-posting",
        headers=_headers(),
        json=_confirmation(),
    )
    assert response.status_code == 403
    assert repository.post_calls == []


def test_posting_controls_require_management_role() -> None:
    client, repository = _client(role="office_staff")
    response = client.get(
        f"/api/v1/management/accounting/loan-disbursements/{EVENT_ID}/journal-posting",
        headers=_headers(),
    )
    assert response.status_code == 403
    assert repository.load_calls == []
