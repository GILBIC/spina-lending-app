from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.loan_disbursement_journal_draft_api import (
    loan_disbursement_journal_draft_repository_dependency,
)
from gilbic_backend.loan_disbursement_journal_draft_repository import (
    LoanDisbursementJournalDraftReview,
    LoanDisbursementJournalDraftStatus,
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
REVIEW_TOKEN = "b" * 64
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
            "accounting.loan_disbursement.journal.prepare",
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


def _review() -> LoanDisbursementJournalDraftReview:
    return LoanDisbursementJournalDraftReview(
        disbursement_event_id=EVENT_ID,
        loan_id=LOAN_ID,
        loan_number="LN-0001",
        client_id=CLIENT_ID,
        client_code="CL-0001",
        client_name="Synthetic Review Client",
        posting_date=date(2026, 8, 11),
        fiscal_period_id=PERIOD_ID,
        source_event_key=SOURCE_KEY,
        external_reference="REL-0001",
        debit_account_id=DEBIT_ID,
        debit_account_system_key="loans_receivable_regular",
        debit_amount=Decimal("5000.00"),
        credit_account_id=CREDIT_ID,
        credit_account_system_key="cash_office",
        credit_amount=Decimal("5000.00"),
        initial_measurement_basis="transaction_price_plain_cash_v1",
        coordinate_policy_version="new_loan_disbursement_coordinates_v1",
        draft_policy_version="new_loan_disbursement_journal_draft_v1",
        review_token=REVIEW_TOKEN,
    )


def _status() -> LoanDisbursementJournalDraftStatus:
    return LoanDisbursementJournalDraftStatus(
        preparation_id=PREPARATION_ID,
        disbursement_event_id=EVENT_ID,
        loan_id=LOAN_ID,
        client_id=CLIENT_ID,
        journal_entry_id=JOURNAL_ID,
        source_event_key=SOURCE_KEY,
        review_token=REVIEW_TOKEN,
        coordinate_policy_version="new_loan_disbursement_coordinates_v1",
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
        journal_status="draft",
        entry_number=None,
        prepared_by_user_id=MANAGEMENT_USER_ID,
        prepared_at=datetime(2026, 8, 11, 13, 0, tzinfo=timezone.utc),
        line_count=2,
        total_debit=Decimal("5000.00"),
        total_credit=Decimal("5000.00"),
        draft_integrity_ready=True,
        posting_enabled=False,
        automatic_source_posting_enabled=False,
    )


class FakeRepository:
    def __init__(self, *, existing: bool = False) -> None:
        self.existing = existing
        self.review_calls: list[UUID] = []
        self.status_calls: list[UUID] = []
        self.prepare_calls: list[tuple[UUID, UUID, str]] = []

    def load_review(self, *, disbursement_event_id: UUID):
        self.review_calls.append(disbursement_event_id)
        return _review()

    def load_status(self, *, disbursement_event_id: UUID):
        self.status_calls.append(disbursement_event_id)
        return _status() if self.existing else None

    def prepare(
        self,
        *,
        actor_user_id: UUID,
        disbursement_event_id: UUID,
        expected_review_token: str,
    ):
        self.prepare_calls.append(
            (actor_user_id, disbursement_event_id, expected_review_token)
        )
        return _status()


def _headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Device-Id": "management-device",
    }


def _confirmation(**overrides):
    payload = {
        "confirm": True,
        "review_token": REVIEW_TOKEN,
        "source_event_key": SOURCE_KEY,
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
        "accounting.loan_disbursement.journal.prepare",
    ),
    existing: bool = False,
):
    repository = FakeRepository(existing=existing)
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts(
        role=role,
        permissions=permissions,
    )
    app.dependency_overrides[loan_disbursement_journal_draft_repository_dependency] = (
        lambda: repository
    )
    return TestClient(app), repository


def test_management_review_exposes_exact_confirmation_without_posting() -> None:
    client, repository = _client()
    response = client.get(
        f"/api/v1/management/accounting/loan-disbursements/{EVENT_ID}/journal-draft/review",
        headers=_headers(),
    )
    assert response.status_code == 200
    assert repository.review_calls == [EVENT_ID]
    data = response.json()["data"]["loan_disbursement_journal_draft_review"]
    assert data["review_token"] == REVIEW_TOKEN
    assert data["source_event_key"] == SOURCE_KEY
    assert data["posting_date"] == "2026-08-11"
    assert data["debit_account_system_key"] == "loans_receivable_regular"
    assert data["credit_account_system_key"] == "cash_office"
    assert data["total_debit"] == "5000.00"
    assert data["total_credit"] == "5000.00"
    assert data["posting_enabled"] is False
    assert data["automatic_source_posting_enabled"] is False


def test_exact_management_confirmation_creates_draft_only() -> None:
    client, repository = _client()
    response = client.post(
        f"/api/mobile/v1/management/accounting/loan-disbursements/{EVENT_ID}/journal-draft",
        headers=_headers(),
        json=_confirmation(),
    )
    assert response.status_code == 201
    assert repository.prepare_calls == [(MANAGEMENT_USER_ID, EVENT_ID, REVIEW_TOKEN)]
    data = response.json()["data"]["loan_disbursement_journal_draft"]
    assert data["journal_status"] == "draft"
    assert data["entry_number"] is None
    assert data["draft_integrity_ready"] is True
    assert data["posting_enabled"] is False
    assert data["automatic_source_posting_enabled"] is False


def test_prepare_requires_confirmation_and_every_exact_accounting_field() -> None:
    client, repository = _client()
    response = client.post(
        f"/api/v1/management/accounting/loan-disbursements/{EVENT_ID}/journal-draft",
        headers=_headers(),
        json=_confirmation(confirm=False),
    )
    assert response.status_code == 409
    assert repository.prepare_calls == []

    response = client.post(
        f"/api/v1/management/accounting/loan-disbursements/{EVENT_ID}/journal-draft",
        headers=_headers(),
        json=_confirmation(credit_account_system_key="cash_bank_gcash"),
    )
    assert response.status_code == 409
    assert repository.prepare_calls == []

    response = client.post(
        f"/api/v1/management/accounting/loan-disbursements/{EVENT_ID}/journal-draft",
        headers=_headers(),
        json=_confirmation(total_credit="4999.00"),
    )
    assert response.status_code == 409
    assert repository.prepare_calls == []


def test_exact_retry_uses_existing_immutable_draft_confirmation() -> None:
    client, repository = _client(existing=True)
    response = client.post(
        f"/api/v1/management/accounting/loan-disbursements/{EVENT_ID}/journal-draft",
        headers=_headers(),
        json=_confirmation(),
    )
    assert response.status_code == 201
    assert repository.review_calls == []
    assert repository.prepare_calls == [(MANAGEMENT_USER_ID, EVENT_ID, REVIEW_TOKEN)]


def test_prepare_requires_dedicated_management_permission() -> None:
    client, repository = _client(permissions=("accounting.view",))
    response = client.post(
        f"/api/v1/management/accounting/loan-disbursements/{EVENT_ID}/journal-draft",
        headers=_headers(),
        json=_confirmation(),
    )
    assert response.status_code == 403
    assert repository.prepare_calls == []


def test_controls_require_management_role() -> None:
    client, repository = _client(role="office_staff")
    response = client.get(
        f"/api/v1/management/accounting/loan-disbursements/{EVENT_ID}/journal-draft/review",
        headers=_headers(),
    )
    assert response.status_code == 403
    assert repository.review_calls == []
