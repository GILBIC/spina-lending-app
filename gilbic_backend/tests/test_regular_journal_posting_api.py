from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.main import create_app
from gilbic_backend.regular_journal_posting_api import (
    regular_journal_posting_repository_dependency,
)
from gilbic_backend.regular_journal_posting_repository import RegularJournalPostingStatus


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
MANAGEMENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
LOAN_ID = UUID("33333333-3333-4333-8333-333333333333")
POSTING_SET_ID = UUID("44444444-4444-4444-8444-444444444444")
REVIEW_TOKEN = "a" * 64


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
            "accounting.regular_journal.post",
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


def _status(*, posted: bool = False) -> RegularJournalPostingStatus:
    return RegularJournalPostingStatus(
        loan_id=LOAN_ID,
        review_set_fingerprint=REVIEW_TOKEN,
        expected_transaction_count=2,
        preparation_count=2,
        expected_entry_count=5,
        actual_entry_count=5,
        draft_entry_count=0 if posted else 5,
        posted_entry_count=5 if posted else 0,
        total_debit=Decimal("520.37"),
        total_credit=Decimal("520.37"),
        posting_ready=not posted,
        posting_blocker=None,
        posting_set_id=POSTING_SET_ID if posted else None,
        audit_entry_count=5 if posted else 0,
        posted_by_user_id=MANAGEMENT_USER_ID if posted else None,
        posted_at=(
            datetime(2026, 8, 11, 5, 30, tzinfo=timezone.utc)
            if posted
            else None
        ),
        entry_numbers=(
            (
                "JE-202607-00000001",
                "JE-202608-00000002",
                "JE-202608-00000003",
                "JE-202608-00000004",
                "JE-202608-00000005",
            )
            if posted
            else ()
        ),
    )


class FakeRepository:
    def __init__(self) -> None:
        self.load_calls: list[tuple[UUID, str]] = []
        self.post_calls: list[tuple[UUID, UUID, str]] = []

    def load_status(self, *, loan_id: UUID, review_set_fingerprint: str):
        self.load_calls.append((loan_id, review_set_fingerprint))
        return _status()

    def post(
        self,
        *,
        actor_user_id: UUID,
        loan_id: UUID,
        expected_review_set_fingerprint: str,
    ):
        self.post_calls.append(
            (actor_user_id, loan_id, expected_review_set_fingerprint)
        )
        return _status(posted=True)


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
        "accounting.regular_journal.post",
    ),
):
    repository = FakeRepository()
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts(
        role=role,
        permissions=permissions,
    )
    app.dependency_overrides[regular_journal_posting_repository_dependency] = (
        lambda: repository
    )
    return TestClient(app), repository


def test_management_can_review_exact_regular_posting_status() -> None:
    client, repository = _client()
    response = client.get(
        f"/api/v1/management/financial-accounting/regular-journal-posting/{LOAN_ID}/{REVIEW_TOKEN}",
        headers=_headers(),
    )

    assert response.status_code == 200
    assert repository.load_calls == [(LOAN_ID, REVIEW_TOKEN)]
    data = response.json()["data"]["regular_journal_posting"]
    assert data["review_token"] == REVIEW_TOKEN
    assert data["expected_transaction_count"] == 2
    assert data["expected_entry_count"] == 5
    assert data["total_debit"] == "520.37"
    assert data["total_credit"] == "520.37"
    assert data["posting_ready"] is True
    assert data["posted"] is False
    assert data["regular_journal_posting_enabled"] is True
    assert data["automatic_source_posting_enabled"] is False


def test_explicit_confirmation_posts_complete_review_set() -> None:
    client, repository = _client()
    response = client.post(
        f"/api/mobile/v1/management/financial-accounting/regular-journal-posting/{LOAN_ID}/{REVIEW_TOKEN}",
        headers=_headers(),
        json={
            "confirm": True,
            "expected_transaction_count": 2,
            "expected_entry_count": 5,
            "total_debit": "520.37",
            "total_credit": "520.37",
        },
    )

    assert response.status_code == 200
    assert repository.post_calls == [
        (MANAGEMENT_USER_ID, LOAN_ID, REVIEW_TOKEN)
    ]
    data = response.json()["data"]["regular_journal_posting"]
    assert data["posted"] is True
    assert data["posting_set_id"] == str(POSTING_SET_ID)
    assert data["draft_entry_count"] == 0
    assert data["posted_entry_count"] == 5
    assert data["audit_entry_count"] == 5
    assert len(data["entry_numbers"]) == 5
    assert data["automatic_source_posting_enabled"] is False


def test_post_requires_explicit_confirmation_before_repository_write() -> None:
    client, repository = _client()
    response = client.post(
        f"/api/v1/management/financial-accounting/regular-journal-posting/{LOAN_ID}/{REVIEW_TOKEN}",
        headers=_headers(),
        json={
            "confirm": False,
            "expected_transaction_count": 2,
            "expected_entry_count": 5,
            "total_debit": "520.37",
            "total_credit": "520.37",
        },
    )

    assert response.status_code == 409
    assert repository.post_calls == []


def test_post_rejects_stale_counts_or_totals_before_repository_write() -> None:
    client, repository = _client()
    response = client.post(
        f"/api/v1/management/financial-accounting/regular-journal-posting/{LOAN_ID}/{REVIEW_TOKEN}",
        headers=_headers(),
        json={
            "confirm": True,
            "expected_transaction_count": 2,
            "expected_entry_count": 5,
            "total_debit": "520.38",
            "total_credit": "520.38",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "regular_journal_post_confirmation_stale"
    assert repository.post_calls == []


def test_post_requires_dedicated_management_permission() -> None:
    client, repository = _client(permissions=("accounting.view",))
    response = client.post(
        f"/api/v1/management/financial-accounting/regular-journal-posting/{LOAN_ID}/{REVIEW_TOKEN}",
        headers=_headers(),
        json={
            "confirm": True,
            "expected_transaction_count": 2,
            "expected_entry_count": 5,
            "total_debit": "520.37",
            "total_credit": "520.37",
        },
    )

    assert response.status_code == 403
    assert repository.post_calls == []


def test_regular_posting_requires_management_role() -> None:
    client, repository = _client(role="office_staff")
    response = client.get(
        f"/api/v1/management/financial-accounting/regular-journal-posting/{LOAN_ID}/{REVIEW_TOKEN}",
        headers=_headers(),
    )

    assert response.status_code == 403
    assert repository.load_calls == []
