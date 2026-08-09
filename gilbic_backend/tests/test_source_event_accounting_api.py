from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.main import create_app
from gilbic_backend.source_event_accounting_api import (
    source_event_accounting_repository_dependency,
)
from gilbic_backend.source_event_accounting_preview import CollectionAccountingPreview
from gilbic_backend.source_event_accounting_repository import SourceEventAccountingPreviewPack


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
MANAGEMENT_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
TX_ID = UUID("33333333-3333-4333-8333-333333333333")
CLIENT_ID = UUID("44444444-4444-4444-8444-444444444444")
LOAN_ID = UUID("55555555-5555-4555-8555-555555555555")


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
    def __init__(self, *, role: str = "management", can_view: bool = True) -> None:
        self.role = role
        self.can_view = can_view

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
            permissions=("accounting.view",) if self.can_view else (),
            device_registered=True,
        )


class FakePreviewRepository:
    def __init__(self) -> None:
        self.calls: list[tuple[date | None, date | None, int]] = []

    def load_collection_preview(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 100,
    ) -> SourceEventAccountingPreviewPack:
        self.calls.append((start_date, end_date, limit))
        event = CollectionAccountingPreview(
            transaction_id=TX_ID,
            source_event_key=f"collection:{TX_ID}",
            receipt_number="COL-20260809-000001",
            client_id=CLIENT_ID,
            client_code="C-001",
            client_name="Synthetic Borrower",
            loan_id=LOAN_ID,
            loan_number="L-001",
            loan_type_code="REGULAR",
            loan_type_name="Regular",
            collection_date=date(2026, 8, 9),
            accepted_at=datetime(2026, 8, 9, 1, 0, tzinfo=timezone.utc),
            entry_type="payment",
            amount=Decimal("200.00"),
            is_voided=False,
            voided_at=None,
            disposition="eir_allocation_required",
            posting_eligible=False,
            message="Event-date EIR allocation is required before journal lines can be proposed.",
            proposed_lines=(),
            existing_journal_entry_id=None,
            existing_journal_status=None,
            existing_journal_entry_number=None,
            reversal_entry_id=None,
            reversal_status=None,
            reversal_entry_number=None,
        )
        return SourceEventAccountingPreviewPack(
            cutover_date=date(2026, 8, 8),
            workbook_status="review_ready",
            opening_balance_posted=False,
            opening_balance_entry_number=None,
            account_configuration_ready=True,
            account_configuration_blocker=None,
            automatic_source_posting_enabled=False,
            eir_income_included_in_collection_mapping=False,
            events=(event,),
        )


def _headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Device-Id": "management-device",
    }


def _client(*, role: str = "management", can_view: bool = True):
    app = create_app()
    repository = FakePreviewRepository()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts(
        role=role,
        can_view=can_view,
    )
    app.dependency_overrides[source_event_accounting_repository_dependency] = lambda: repository
    return TestClient(app), repository


def test_management_can_load_read_only_collection_accounting_preview() -> None:
    client, repository = _client()
    response = client.get(
        "/api/mobile/v1/management/financial-accounting/source-events/collections",
        params={"start_date": "2026-08-09", "end_date": "2026-08-10", "limit": 25},
        headers=_headers(),
    )

    assert response.status_code == 200
    assert repository.calls == [(date(2026, 8, 9), date(2026, 8, 10), 25)]
    data = response.json()["data"]["collection_source_events"]
    assert data["automatic_source_posting_enabled"] is False
    assert data["eir_income_included_in_collection_mapping"] is False
    assert data["cutover"]["cutover_date"] == "2026-08-08"
    item = data["events"][0]
    assert item["posting_eligible"] is False
    assert item["source_event_key"] == f"collection:{TX_ID}"
    assert item["disposition"] == "eir_allocation_required"
    assert item["proposed_lines"] == []
    assert "EIR allocation" in item["message"]


def test_invalid_date_range_is_rejected_before_repository_read() -> None:
    client, repository = _client()
    response = client.get(
        "/api/mobile/v1/management/financial-accounting/source-events/collections",
        params={"start_date": "2026-08-10", "end_date": "2026-08-09"},
        headers=_headers(),
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_source_event_date_range"
    assert repository.calls == []


def test_source_event_preview_requires_accounting_view_permission() -> None:
    client, repository = _client(can_view=False)
    response = client.get(
        "/api/mobile/v1/management/financial-accounting/source-events/collections",
        headers=_headers(),
    )
    assert response.status_code == 403
    assert repository.calls == []


def test_source_event_preview_requires_management_role() -> None:
    client, repository = _client(role="collector")
    response = client.get(
        "/api/mobile/v1/management/financial-accounting/source-events/collections",
        headers=_headers(),
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "management_role_required"
    assert repository.calls == []
