from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.loan_disbursement_cancellation_api import (
    loan_disbursement_cancellation_repository_dependency,
)
from gilbic_backend.loan_disbursement_cancellation_repository import (
    LoanDisbursementCancellationStatus,
)
from gilbic_backend.main import create_app


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
MANAGEMENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
EVENT_ID = UUID("33333333-3333-4333-8333-333333333333")
LOAN_ID = UUID("44444444-4444-4444-8444-444444444444")
CLIENT_ID = UUID("55555555-5555-4555-8555-555555555555")
PREPARATION_ID = UUID("66666666-6666-4666-8666-666666666666")
POSTING_ID = UUID("77777777-7777-4777-8777-777777777777")
ORIGINAL_JOURNAL_ID = UUID("88888888-8888-4888-8888-888888888888")
DEBIT_ID = UUID("99999999-9999-4999-8999-999999999999")
CREDIT_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
CANCELLATION_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
REVERSAL_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
REVERSAL_JOURNAL_ID = UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
POSTING_TOKEN = "e" * 64
CANCELLATION_TOKEN = "f" * 64
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
            "accounting.loan_disbursement.journal.reverse",
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


def _status(*, cancelled: bool = False) -> LoanDisbursementCancellationStatus:
    return LoanDisbursementCancellationStatus(
        posting_id=POSTING_ID,
        preparation_id=PREPARATION_ID,
        disbursement_event_id=EVENT_ID,
        loan_id=LOAN_ID,
        client_id=CLIENT_ID,
        original_journal_entry_id=ORIGINAL_JOURNAL_ID,
        original_entry_number="JE-202608-00000001",
        original_source_event_key=SOURCE_KEY,
        posting_review_token=POSTING_TOKEN,
        amount=Decimal("5000.00"),
        original_debit_account_id=DEBIT_ID,
        original_debit_account_system_key="loans_receivable_regular",
        original_credit_account_id=CREDIT_ID,
        original_credit_account_system_key="cash_office",
        original_journal_status="posted",
        cancellation_id=CANCELLATION_ID if cancelled else None,
        cancellation_source_key=(
            f"loan_disbursement_cancellation:{EVENT_ID}" if cancelled else None
        ),
        reversal_posting_date=date(2026, 8, 12) if cancelled else None,
        cancellation_reason="Release cancelled before borrower received funds" if cancelled else None,
        cancelled_by_user_id=MANAGEMENT_USER_ID if cancelled else None,
        cancelled_at=(
            datetime(2026, 8, 12, 2, 0, tzinfo=timezone.utc)
            if cancelled
            else None
        ),
        reversal_id=REVERSAL_ID if cancelled else None,
        reversal_journal_entry_id=REVERSAL_JOURNAL_ID if cancelled else None,
        reversal_entry_number="JE-202608-00000002" if cancelled else None,
        reversal_source_event_key=(
            f"loan_disbursement_cancellation_reversal:{POSTING_ID}"
            if cancelled
            else None
        ),
        reversal_journal_status="posted" if cancelled else None,
        cancellation_ready=not cancelled,
        cancelled_reversal_audit_exact=cancelled,
        protected_reversal_enabled=True,
        automatic_source_posting_enabled=False,
        cancellation_review_token=CANCELLATION_TOKEN,
    )


class FakeRepository:
    def __init__(self, *, cancelled: bool = False) -> None:
        self.cancelled = cancelled
        self.load_calls: list[UUID] = []
        self.reverse_calls: list[tuple[UUID, UUID, str, date, str]] = []

    def load_status(self, *, disbursement_event_id: UUID):
        self.load_calls.append(disbursement_event_id)
        return _status(cancelled=self.cancelled)

    def reverse(
        self,
        *,
        actor_user_id: UUID,
        disbursement_event_id: UUID,
        expected_cancellation_review_token: str,
        reversal_posting_date: date,
        reason: str,
    ):
        self.reverse_calls.append(
            (
                actor_user_id,
                disbursement_event_id,
                expected_cancellation_review_token,
                reversal_posting_date,
                reason,
            )
        )
        self.cancelled = True
        return _status(cancelled=True)


def _headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Device-Id": "management-device",
    }


def _confirmation(**overrides):
    payload = {
        "confirm": True,
        "cancellation_review_token": CANCELLATION_TOKEN,
        "posting_id": str(POSTING_ID),
        "original_journal_entry_id": str(ORIGINAL_JOURNAL_ID),
        "original_entry_number": "JE-202608-00000001",
        "original_source_event_key": SOURCE_KEY,
        "amount": "5000.00",
        "original_debit_account_system_key": "loans_receivable_regular",
        "original_credit_account_system_key": "cash_office",
        "reversal_posting_date": "2026-08-12",
        "reason": "Release cancelled before borrower received funds",
    }
    payload.update(overrides)
    return payload


def _client(
    *,
    role: str = "management",
    permissions: tuple[str, ...] = (
        "accounting.view",
        "accounting.loan_disbursement.journal.reverse",
    ),
    cancelled: bool = False,
):
    repository = FakeRepository(cancelled=cancelled)
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts(
        role=role,
        permissions=permissions,
    )
    app.dependency_overrides[loan_disbursement_cancellation_repository_dependency] = (
        lambda: repository
    )
    return TestClient(app), repository


def test_management_cancellation_review_exposes_original_posted_facts_and_auto_off() -> None:
    client, repository = _client()
    response = client.get(
        f"/api/v1/management/accounting/loan-disbursements/{EVENT_ID}/journal-cancellation",
        headers=_headers(),
    )
    assert response.status_code == 200
    assert repository.load_calls == [EVENT_ID]
    data = response.json()["data"]["loan_disbursement_cancellation"]
    assert data["posting_id"] == str(POSTING_ID)
    assert data["original_journal_entry_id"] == str(ORIGINAL_JOURNAL_ID)
    assert data["original_entry_number"] == "JE-202608-00000001"
    assert data["original_source_event_key"] == SOURCE_KEY
    assert data["amount"] == "5000.00"
    assert data["original_debit_account_system_key"] == "loans_receivable_regular"
    assert data["original_credit_account_system_key"] == "cash_office"
    assert data["cancellation_review_token"] == CANCELLATION_TOKEN
    assert data["cancellation_ready"] is True
    assert data["cancelled"] is False
    assert data["automatic_source_posting_enabled"] is False


def test_exact_management_confirmation_cancels_and_reverses_once() -> None:
    client, repository = _client()
    response = client.post(
        f"/api/mobile/v1/management/accounting/loan-disbursements/{EVENT_ID}/journal-cancellation",
        headers=_headers(),
        json=_confirmation(),
    )
    assert response.status_code == 200
    assert repository.reverse_calls == [
        (
            MANAGEMENT_USER_ID,
            EVENT_ID,
            CANCELLATION_TOKEN,
            date(2026, 8, 12),
            "Release cancelled before borrower received funds",
        )
    ]
    data = response.json()["data"]["loan_disbursement_cancellation"]
    assert data["cancelled"] is True
    assert data["cancelled_reversal_audit_exact"] is True
    assert data["reversal_journal_status"] == "posted"
    assert data["reversal_entry_number"] == "JE-202608-00000002"
    assert data["automatic_source_posting_enabled"] is False


def test_cancellation_requires_explicit_confirmation_and_every_exact_posted_field() -> None:
    client, repository = _client()
    response = client.post(
        f"/api/v1/management/accounting/loan-disbursements/{EVENT_ID}/journal-cancellation",
        headers=_headers(),
        json=_confirmation(confirm=False),
    )
    assert response.status_code == 409
    assert repository.reverse_calls == []

    for override in (
        {"cancellation_review_token": "0" * 64},
        {"posting_id": "77777777-7777-4777-8777-777777777778"},
        {"original_journal_entry_id": "88888888-8888-4888-8888-888888888889"},
        {"original_entry_number": "JE-202608-99999999"},
        {"amount": "4999.00"},
        {"original_credit_account_system_key": "cash_bank_gcash"},
    ):
        response = client.post(
            f"/api/v1/management/accounting/loan-disbursements/{EVENT_ID}/journal-cancellation",
            headers=_headers(),
            json=_confirmation(**override),
        )
        assert response.status_code == 409
    assert repository.reverse_calls == []


def test_exact_retry_is_allowed_for_same_immutable_cancellation() -> None:
    client, repository = _client(cancelled=True)
    response = client.post(
        f"/api/v1/management/accounting/loan-disbursements/{EVENT_ID}/journal-cancellation",
        headers=_headers(),
        json=_confirmation(),
    )
    assert response.status_code == 200
    assert repository.reverse_calls == [
        (
            MANAGEMENT_USER_ID,
            EVENT_ID,
            CANCELLATION_TOKEN,
            date(2026, 8, 12),
            "Release cancelled before borrower received funds",
        )
    ]
    assert response.json()["data"]["loan_disbursement_cancellation"]["cancelled"] is True


def test_cancellation_requires_dedicated_management_permission() -> None:
    client, repository = _client(permissions=("accounting.view",))
    response = client.post(
        f"/api/v1/management/accounting/loan-disbursements/{EVENT_ID}/journal-cancellation",
        headers=_headers(),
        json=_confirmation(),
    )
    assert response.status_code == 403
    assert repository.reverse_calls == []


def test_cancellation_controls_require_management_role() -> None:
    client, repository = _client(role="office_staff")
    response = client.get(
        f"/api/v1/management/accounting/loan-disbursements/{EVENT_ID}/journal-cancellation",
        headers=_headers(),
    )
    assert response.status_code == 403
    assert repository.load_calls == []
