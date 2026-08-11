from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.main import create_app
from gilbic_backend.regular_journal_draft_api import (
    regular_journal_draft_repository_dependency,
)
from gilbic_backend.regular_journal_draft_repository import (
    RegularJournalDraftEntryStatus,
    RegularJournalDraftPreparationStatus,
    RegularJournalDraftReview,
    RegularJournalDraftReviewBundle,
    RegularJournalDraftReviewSetStatus,
)


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
MANAGEMENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
LOAN_ID = UUID("33333333-3333-4333-8333-333333333333")
TX_ID = UUID("44444444-4444-4444-8444-444444444444")
PREPARATION_ID = UUID("55555555-5555-4555-8555-555555555555")
EIR_ENTRY_ID = UUID("66666666-6666-4666-8666-666666666666")
CASH_ENTRY_ID = UUID("77777777-7777-4777-8777-777777777777")
JULY_ID = UUID("88888888-8888-4888-8888-888888888888")
AUGUST_ID = UUID("99999999-9999-4999-8999-999999999999")
REVIEW_TOKEN = "a" * 64
BUNDLE_TOKEN = "b" * 64


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
            "accounting.regular_journal.prepare",
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


def _entry(
    *,
    entry_id: UUID,
    sequence_order: int,
    entry_type: str,
    source_type: str,
    source_reference: str,
    source_event_key: str,
    posting_date: date,
    period_id: UUID,
    period_label: str,
    amount: str,
) -> RegularJournalDraftEntryStatus:
    value = Decimal(amount)
    return RegularJournalDraftEntryStatus(
        transaction_id=TX_ID,
        sequence_order=sequence_order,
        entry_type=entry_type,
        journal_entry_id=entry_id,
        journal_status="draft",
        source_type=source_type,
        source_reference=source_reference,
        source_event_key=source_event_key,
        posting_date=posting_date,
        fiscal_period_id=period_id,
        fiscal_period_label=period_label,
        fiscal_period_status="open",
        line_count=2,
        total_debit=value,
        total_credit=value,
        balanced=True,
    )


def _review() -> RegularJournalDraftReview:
    return RegularJournalDraftReview(
        loan_id=LOAN_ID,
        review_set_fingerprint=REVIEW_TOKEN,
        evidence_policy_version="regular_cross_period_posting_ready_evidence_v1",
        draft_policy_version="regular_journal_draft_v1",
        transaction_count=1,
        bundles=(
            RegularJournalDraftReviewBundle(
                transaction_id=TX_ID,
                bundle_fingerprint=BUNDLE_TOKEN,
                expected_entry_count=2,
            ),
        ),
    )


def _status() -> RegularJournalDraftReviewSetStatus:
    prepared_at = datetime(2026, 8, 11, 1, 30, tzinfo=timezone.utc)
    preparation = RegularJournalDraftPreparationStatus(
        preparation_id=PREPARATION_ID,
        loan_id=LOAN_ID,
        transaction_id=TX_ID,
        review_set_fingerprint=REVIEW_TOKEN,
        bundle_fingerprint=BUNDLE_TOKEN,
        evidence_policy_version="regular_cross_period_posting_ready_evidence_v1",
        draft_policy_version="regular_journal_draft_v1",
        expected_set_transaction_count=1,
        expected_entry_count=2,
        prepared_by_user_id=MANAGEMENT_USER_ID,
        prepared_at=prepared_at,
        actual_entry_count=2,
        draft_entry_count=2,
        posted_entry_count=0,
        total_debit=Decimal("1.01"),
        total_credit=Decimal("1.01"),
        draft_integrity_ready=True,
        regular_journal_posting_enabled=False,
        automatic_source_posting_enabled=False,
        draft_integrity_blocker=None,
        entries=(
            _entry(
                entry_id=EIR_ENTRY_ID,
                sequence_order=1,
                entry_type="eir_accrual_period",
                source_type="regular_eir_accrual",
                source_reference=f"{TX_ID}:fiscal_period:{JULY_ID}",
                source_event_key=(
                    f"eir_accrual:collection:{TX_ID}:fiscal_period:{JULY_ID}"
                ),
                posting_date=date(2026, 7, 31),
                period_id=JULY_ID,
                period_label="July 2026",
                amount="0.01",
            ),
            _entry(
                entry_id=CASH_ENTRY_ID,
                sequence_order=2,
                entry_type="collection",
                source_type="collection",
                source_reference=str(TX_ID),
                source_event_key=f"collection:{TX_ID}",
                posting_date=date(2026, 8, 1),
                period_id=AUGUST_ID,
                period_label="August 2026",
                amount="1.00",
            ),
        ),
    )
    return RegularJournalDraftReviewSetStatus(
        loan_id=LOAN_ID,
        review_set_fingerprint=REVIEW_TOKEN,
        expected_transaction_count=1,
        preparation_count=1,
        draft_integrity_ready=True,
        regular_journal_posting_enabled=False,
        automatic_source_posting_enabled=False,
        blocker=None,
        preparations=(preparation,),
    )


class FakeRepository:
    def __init__(self) -> None:
        self.review_calls: list[UUID] = []
        self.list_calls: list[UUID] = []
        self.prepare_calls: list[tuple[UUID, UUID, str]] = []

    def load_review(self, *, loan_id: UUID):
        self.review_calls.append(loan_id)
        return _review()

    def list_status(self, *, loan_id: UUID):
        self.list_calls.append(loan_id)
        return (_status(),)

    def prepare(
        self,
        *,
        actor_user_id: UUID,
        loan_id: UUID,
        expected_review_set_fingerprint: str,
    ):
        self.prepare_calls.append(
            (actor_user_id, loan_id, expected_review_set_fingerprint)
        )
        return _status()


def _headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Device-Id": "management-device",
    }


def _client(
    *,
    role: str = "management",
    permissions: tuple[str, ...] = (
        "accounting.view",
        "accounting.regular_journal.prepare",
    ),
):
    repository = FakeRepository()
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts(
        role=role,
        permissions=permissions,
    )
    app.dependency_overrides[regular_journal_draft_repository_dependency] = (
        lambda: repository
    )
    return TestClient(app), repository


def test_management_can_read_stale_safe_draft_review_token_without_writes() -> None:
    client, repository = _client()
    response = client.get(
        f"/api/v1/management/financial-accounting/regular-journal-drafts/{LOAN_ID}/review",
        headers=_headers(),
    )

    assert response.status_code == 200
    assert repository.review_calls == [LOAN_ID]
    data = response.json()["data"]["regular_journal_draft_review"]
    assert data["review_token"] == REVIEW_TOKEN
    assert data["transaction_count"] == 1
    assert data["transactions"] == [
        {
            "transaction_id": str(TX_ID),
            "bundle_fingerprint": BUNDLE_TOKEN,
            "expected_entry_count": 2,
        }
    ]
    assert data["posting_eligible"] is False
    assert data["automatic_source_posting_enabled"] is False


def test_management_explicit_confirmation_creates_only_protected_draft_set() -> None:
    client, repository = _client()
    response = client.post(
        f"/api/mobile/v1/management/financial-accounting/regular-journal-drafts/{LOAN_ID}",
        headers=_headers(),
        json={"confirm": True, "review_token": REVIEW_TOKEN},
    )

    assert response.status_code == 201
    assert repository.prepare_calls == [
        (MANAGEMENT_USER_ID, LOAN_ID, REVIEW_TOKEN)
    ]
    data = response.json()["data"]["regular_journal_draft_review_set"]
    assert data["review_token"] == REVIEW_TOKEN
    assert data["draft_integrity_ready"] is True
    assert data["regular_journal_posting_enabled"] is False
    assert data["automatic_source_posting_enabled"] is False
    assert len(data["preparations"]) == 1
    preparation = data["preparations"][0]
    assert preparation["draft_entry_count"] == 2
    assert preparation["posted_entry_count"] == 0
    assert [entry["journal_status"] for entry in preparation["entries"]] == [
        "draft",
        "draft",
    ]
    assert all(
        entry["posting_enabled"] is False
        for entry in preparation["entries"]
    )


def test_status_endpoint_exposes_protected_drafts_without_post_action() -> None:
    client, repository = _client()
    response = client.get(
        f"/api/mobile/v1/management/financial-accounting/regular-journal-drafts/{LOAN_ID}",
        headers=_headers(),
    )

    assert response.status_code == 200
    assert repository.list_calls == [LOAN_ID]
    data = response.json()["data"]["regular_journal_drafts"]
    assert len(data["review_sets"]) == 1
    assert data["regular_journal_posting_enabled"] is False
    assert data["automatic_source_posting_enabled"] is False


def test_prepare_requires_explicit_confirmation_before_repository_call() -> None:
    client, repository = _client()
    response = client.post(
        f"/api/v1/management/financial-accounting/regular-journal-drafts/{LOAN_ID}",
        headers=_headers(),
        json={"confirm": False, "review_token": REVIEW_TOKEN},
    )

    assert response.status_code == 409
    assert repository.prepare_calls == []


def test_prepare_requires_dedicated_permission() -> None:
    client, repository = _client(permissions=("accounting.view",))
    response = client.post(
        f"/api/v1/management/financial-accounting/regular-journal-drafts/{LOAN_ID}",
        headers=_headers(),
        json={"confirm": True, "review_token": REVIEW_TOKEN},
    )

    assert response.status_code == 403
    assert repository.prepare_calls == []


def test_regular_journal_draft_controls_require_management_role() -> None:
    client, repository = _client(role="office_staff")
    response = client.get(
        f"/api/v1/management/financial-accounting/regular-journal-drafts/{LOAN_ID}/review",
        headers=_headers(),
    )

    assert response.status_code == 403
    assert repository.review_calls == []
