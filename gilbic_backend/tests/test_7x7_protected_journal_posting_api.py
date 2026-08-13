from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.main import create_app
from gilbic_backend.seven_by_seven_journal_posting_api import (
    seven_by_seven_journal_posting_repository_dependency,
)
from gilbic_backend.seven_by_seven_journal_posting_repository import (
    SevenBySevenJournalPostingStatus,
)


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
MANAGEMENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
TRANSACTION_ID = UUID("33333333-3333-4333-8333-333333333333")
LOAN_ID = UUID("44444444-4444-4444-8444-444444444444")
CLIENT_ID = UUID("55555555-5555-4555-8555-555555555555")
PERIOD_ID = UUID("66666666-6666-4666-8666-666666666666")
PREPARATION_ID = UUID("77777777-7777-4777-8777-777777777777")
JOURNAL_ID = UUID("88888888-8888-4888-8888-888888888888")
POSTING_ID = UUID("99999999-9999-4999-8999-999999999999")
SOURCE_TOKEN = "a" * 64
COORDINATE_DIGEST = "b" * 64
POSTING_TOKEN = "c" * 64
SOURCE_KEY = f"collection:{TRANSACTION_ID}"


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
            "accounting.seven_by_seven.journal.post",
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


def _status(*, posted: bool = False) -> SevenBySevenJournalPostingStatus:
    return SevenBySevenJournalPostingStatus(
        preparation_id=PREPARATION_ID,
        transaction_id=TRANSACTION_ID,
        loan_id=LOAN_ID,
        client_id=CLIENT_ID,
        journal_entry_id=JOURNAL_ID,
        source_event_key=SOURCE_KEY,
        source_event_review_token=SOURCE_TOKEN,
        coordinate_digest=COORDINATE_DIGEST,
        draft_policy_version="seven_by_seven_source_event_journal_draft_v1",
        posting_date=date(2026, 8, 12),
        fiscal_period_id=PERIOD_ID,
        fiscal_period_label="August 2026",
        fiscal_period_status="open",
        source_cash_amount=Decimal("50.00"),
        eir_interest_accrual=Decimal("0.25"),
        accounting_eir_interest_received=Decimal("0.25"),
        accounting_7x7_principal_received=Decimal("49.75"),
        coordinate_line_count=5,
        prepared_total_debit=Decimal("50.25"),
        prepared_total_credit=Decimal("50.25"),
        prepared_by_user_id=MANAGEMENT_USER_ID,
        prepared_at=datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc),
        journal_status="posted" if posted else "draft",
        entry_number="JE-202608-00000001" if posted else None,
        line_count=5,
        total_debit=Decimal("50.25"),
        total_credit=Decimal("50.25"),
        posting_id=POSTING_ID if posted else None,
        posting_review_token=POSTING_TOKEN,
        posting_policy_version="seven_by_seven_source_event_journal_posting_v1",
        posted_by_user_id=MANAGEMENT_USER_ID if posted else None,
        posted_at=(
            datetime(2026, 8, 12, 12, 30, tzinfo=timezone.utc)
            if posted
            else None
        ),
        posting_ready=not posted,
        posted_audit_exact=posted,
        protected_posting_enabled=True,
        reversal_enabled=False,
        automatic_source_posting_enabled=False,
    )


class FakeRepository:
    def __init__(self, *, posted: bool = False) -> None:
        self.posted = posted
        self.load_calls: list[UUID] = []
        self.post_calls: list[tuple[UUID, UUID, str]] = []

    def load_status(self, *, transaction_id: UUID):
        self.load_calls.append(transaction_id)
        return _status(posted=self.posted)

    def post(
        self,
        *,
        actor_user_id: UUID,
        transaction_id: UUID,
        expected_posting_review_token: str,
    ):
        self.post_calls.append(
            (actor_user_id, transaction_id, expected_posting_review_token)
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
        "source_event_review_token": SOURCE_TOKEN,
        "coordinate_digest": COORDINATE_DIGEST,
        "posting_date": "2026-08-12",
        "fiscal_period_id": str(PERIOD_ID),
        "source_cash_amount": "50.00",
        "eir_interest_accrual": "0.25",
        "accounting_eir_interest_received": "0.25",
        "accounting_7x7_principal_received": "49.75",
        "coordinate_line_count": 5,
        "total_debit": "50.25",
        "total_credit": "50.25",
    }
    payload.update(overrides)
    return payload


def _client(
    *,
    role: str = "management",
    permissions: tuple[str, ...] = (
        "accounting.view",
        "accounting.seven_by_seven.journal.post",
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
    app.dependency_overrides[seven_by_seven_journal_posting_repository_dependency] = (
        lambda: repository
    )
    return TestClient(app), repository


def test_management_review_exposes_exact_eir_confirmation_and_safety_flags() -> None:
    client, repository = _client()
    response = client.get(
        f"/api/v1/management/accounting/seven-by-seven/collections/{TRANSACTION_ID}/journal-posting",
        headers=_headers(),
    )
    assert response.status_code == 200
    assert repository.load_calls == [TRANSACTION_ID]
    data = response.json()["data"]["seven_by_seven_journal_posting"]
    assert data["source_event_key"] == SOURCE_KEY
    assert data["source_event_review_token"] == SOURCE_TOKEN
    assert data["coordinate_digest"] == COORDINATE_DIGEST
    assert data["posting_review_token"] == POSTING_TOKEN
    assert data["source_cash_amount"] == "50.00"
    assert data["eir_interest_accrual"] == "0.25"
    assert data["accounting_eir_interest_received"] == "0.25"
    assert data["accounting_7x7_principal_received"] == "49.75"
    assert data["posting_ready"] is True
    assert data["posted"] is False
    assert data["reversal_enabled"] is False
    assert data["automatic_source_posting_enabled"] is False


def test_exact_management_confirmation_posts_once() -> None:
    client, repository = _client()
    response = client.post(
        f"/api/mobile/v1/management/accounting/seven-by-seven/collections/{TRANSACTION_ID}/journal-posting",
        headers=_headers(),
        json=_confirmation(),
    )
    assert response.status_code == 200
    assert repository.post_calls == [
        (MANAGEMENT_USER_ID, TRANSACTION_ID, POSTING_TOKEN)
    ]
    data = response.json()["data"]["seven_by_seven_journal_posting"]
    assert data["journal_status"] == "posted"
    assert data["entry_number"] == "JE-202608-00000001"
    assert data["posted"] is True
    assert data["posted_audit_exact"] is True
    assert data["reversal_enabled"] is False
    assert data["automatic_source_posting_enabled"] is False


def test_post_requires_explicit_confirmation_and_every_exact_field() -> None:
    client, repository = _client()
    response = client.post(
        f"/api/v1/management/accounting/seven-by-seven/collections/{TRANSACTION_ID}/journal-posting",
        headers=_headers(),
        json=_confirmation(confirm=False),
    )
    assert response.status_code == 409
    assert repository.post_calls == []

    for override in (
        {"posting_review_token": "d" * 64},
        {"coordinate_digest": "e" * 64},
        {"source_cash_amount": "49.00"},
        {"eir_interest_accrual": "0.24"},
        {"accounting_7x7_principal_received": "48.75"},
        {"coordinate_line_count": 4},
        {"total_credit": "50.24"},
        {"fiscal_period_id": "66666666-6666-4666-8666-666666666667"},
    ):
        response = client.post(
            f"/api/v1/management/accounting/seven-by-seven/collections/{TRANSACTION_ID}/journal-posting",
            headers=_headers(),
            json=_confirmation(**override),
        )
        assert response.status_code == 409
    assert repository.post_calls == []


def test_exact_retry_is_allowed_only_for_audit_exact_posted_state() -> None:
    client, repository = _client(posted=True)
    response = client.post(
        f"/api/v1/management/accounting/seven-by-seven/collections/{TRANSACTION_ID}/journal-posting",
        headers=_headers(),
        json=_confirmation(),
    )
    assert response.status_code == 200
    assert repository.post_calls == [
        (MANAGEMENT_USER_ID, TRANSACTION_ID, POSTING_TOKEN)
    ]
    assert response.json()["data"]["seven_by_seven_journal_posting"]["posted"] is True


def test_post_requires_dedicated_management_permission() -> None:
    client, repository = _client(permissions=("accounting.view",))
    response = client.post(
        f"/api/v1/management/accounting/seven-by-seven/collections/{TRANSACTION_ID}/journal-posting",
        headers=_headers(),
        json=_confirmation(),
    )
    assert response.status_code == 403
    assert repository.post_calls == []


def test_posting_controls_require_management_role() -> None:
    client, repository = _client(role="office_staff")
    response = client.get(
        f"/api/v1/management/accounting/seven-by-seven/collections/{TRANSACTION_ID}/journal-posting",
        headers=_headers(),
    )
    assert response.status_code == 403
    assert repository.load_calls == []
