from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from gilbic_backend.account_repository import AccountContext
from gilbic_backend.auth_api import account_repository_dependency, auth_client_dependency
from gilbic_backend.auth_client import AuthSession
from gilbic_backend.collector_schedule_api import (
    collector_schedule_repository_dependency,
)
from gilbic_backend.collector_schedule_repository import (
    CollectorScheduleRecord,
    CollectorScheduleRowRecord,
    _build_installment_row,
)
from gilbic_backend.main import create_app


AUTH_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
COLLECTOR_USER_ID = UUID("22222222-2222-4222-8222-222222222222")
CLIENT_ID = UUID("33333333-3333-4333-8333-333333333333")
LOAN_ID = UUID("44444444-4444-4444-8444-444444444444")
SCHEDULE_ID = UUID("55555555-5555-4555-8555-555555555555")


class FakeAuthClient:
    def get_user(self, *, access_token: str) -> AuthSession:
        assert access_token == "collector-token"
        return AuthSession(
            auth_user_id=AUTH_USER_ID,
            email="collector@example.com",
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
        assert device_identifier == "collector-device"
        return AccountContext(
            user_id=COLLECTOR_USER_ID,
            auth_user_id=AUTH_USER_ID,
            username="collector.one",
            email="collector@example.com",
            full_name="Collector One",
            status="active",
            roles=("collector",),
            permissions=("route.view",),
            device_registered=True,
        )


class FakeSchedules:
    def __init__(self) -> None:
        self.request: tuple[UUID, UUID, date] | None = None

    def get_schedule(
        self,
        *,
        collector_user_id: UUID,
        loan_id: UUID,
        as_of_date: date,
    ) -> CollectorScheduleRecord:
        self.request = (collector_user_id, loan_id, as_of_date)
        return CollectorScheduleRecord(
            loan_id=LOAN_ID,
            loan_number="LN-1001",
            client_id=CLIENT_ID,
            client_name="Ana Client",
            loan_type="Regular",
            calculation_mode="fixed_total",
            schedule_id=SCHEDULE_ID,
            schedule_version=3,
            payment_frequency="daily",
            contract_reference="CTR-1001",
            as_of_date=as_of_date,
            rows=(
                CollectorScheduleRowRecord(
                    kind="installment",
                    schedule_date=date(2026, 8, 26),
                    status="Due Today",
                    amount=Decimal("100.00"),
                    contractual_amount=Decimal("100.00"),
                    paid_amount=Decimal("0.00"),
                    prepaid_amount=Decimal("0.00"),
                    remaining_amount=Decimal("100.00"),
                    installment_id=10,
                    installment_number=10,
                    contractual_due_date=date(2026, 8, 26),
                ),
                CollectorScheduleRowRecord(
                    kind="no_collection",
                    schedule_date=date(2026, 8, 27),
                    status="No Collection",
                    amount=Decimal("0.00"),
                    contractual_amount=Decimal("0.00"),
                    paid_amount=Decimal("0.00"),
                    prepaid_amount=Decimal("0.00"),
                    remaining_amount=Decimal("0.00"),
                    no_collection_reason="Typhoon suspension",
                ),
            ),
        )


def _client() -> tuple[TestClient, FakeSchedules]:
    schedules = FakeSchedules()
    app = create_app()
    app.dependency_overrides[auth_client_dependency] = lambda: FakeAuthClient()
    app.dependency_overrides[account_repository_dependency] = lambda: FakeAccounts()
    app.dependency_overrides[collector_schedule_repository_dependency] = lambda: schedules
    return TestClient(app), schedules


def _headers() -> dict[str, str]:
    return {
        "Authorization": "Bearer collector-token",
        "X-Device-Id": "collector-device",
    }


def test_collector_view_schedule_is_read_only_and_route_scoped() -> None:
    client, schedules = _client()

    response = client.get(
        f"/api/mobile/v1/collector/loans/{LOAN_ID}/schedule",
        headers=_headers(),
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["loan_id"] == str(LOAN_ID)
    assert payload["client_name"] == "Ana Client"
    assert payload["read_only"] is True
    assert payload["rows"][0]["date"] == "2026-08-26"
    assert payload["rows"][0]["amount"] == "100.00"
    assert payload["rows"][0]["status"] == "Due Today"
    assert payload["rows"][1]["status"] == "No Collection"
    assert payload["rows"][1]["no_collection_reason"] == "Typhoon suspension"
    assert schedules.request is not None
    assert schedules.request[0] == COLLECTOR_USER_ID
    assert schedules.request[1] == LOAN_ID


def test_future_advance_states_are_visible_without_manual_date_selection() -> None:
    full = _build_installment_row(
        as_of_date=date(2026, 8, 26),
        installment_id=1,
        installment_number=1,
        contractual_due_date=date(2026, 8, 27),
        effective_due_date=date(2026, 8, 27),
        contractual_amount=Decimal("100.00"),
        paid_amount=Decimal("100.00"),
        prepaid_amount=Decimal("100.00"),
        principal_reduction_amount=Decimal("0.00"),
        principal_component=None,
        interest_component=None,
    )
    partial = _build_installment_row(
        as_of_date=date(2026, 8, 26),
        installment_id=2,
        installment_number=2,
        contractual_due_date=date(2026, 8, 28),
        effective_due_date=date(2026, 8, 28),
        contractual_amount=Decimal("100.00"),
        paid_amount=Decimal("50.00"),
        prepaid_amount=Decimal("50.00"),
        principal_reduction_amount=Decimal("0.00"),
        principal_component=None,
        interest_component=None,
    )

    assert full is not None
    assert full.status == "Paid in Advance"
    assert full.remaining_amount == Decimal("0.00")
    assert partial is not None
    assert partial.status == "Partially Paid in Advance"
    assert partial.remaining_amount == Decimal("50.00")


def test_principal_reduction_updates_current_schedule_without_special_status() -> None:
    partial_tail = _build_installment_row(
        as_of_date=date(2026, 8, 26),
        installment_id=3,
        installment_number=3,
        contractual_due_date=date(2026, 8, 30),
        effective_due_date=date(2026, 8, 30),
        contractual_amount=Decimal("100.00"),
        paid_amount=Decimal("0.00"),
        prepaid_amount=Decimal("0.00"),
        principal_reduction_amount=Decimal("50.00"),
        principal_component=None,
        interest_component=None,
    )
    removed_tail = _build_installment_row(
        as_of_date=date(2026, 8, 26),
        installment_id=4,
        installment_number=4,
        contractual_due_date=date(2026, 8, 31),
        effective_due_date=date(2026, 8, 31),
        contractual_amount=Decimal("100.00"),
        paid_amount=Decimal("0.00"),
        prepaid_amount=Decimal("0.00"),
        principal_reduction_amount=Decimal("100.00"),
        principal_component=None,
        interest_component=None,
    )

    assert partial_tail is not None
    assert partial_tail.amount == Decimal("50.00")
    assert partial_tail.status == "Scheduled"
    assert partial_tail.principal_reduction_amount == Decimal("50.00")
    assert removed_tail is None


def test_partial_past_due_row_stays_past_due_for_collection_guidance() -> None:
    row = _build_installment_row(
        as_of_date=date(2026, 8, 26),
        installment_id=5,
        installment_number=5,
        contractual_due_date=date(2026, 8, 24),
        effective_due_date=date(2026, 8, 24),
        contractual_amount=Decimal("100.00"),
        paid_amount=Decimal("40.00"),
        prepaid_amount=Decimal("0.00"),
        principal_reduction_amount=Decimal("0.00"),
        principal_component=None,
        interest_component=None,
        past_due_reason_code="business_slow",
        past_due_reason_note="Sales were low",
    )

    assert row is not None
    assert row.status == "Past Due"
    assert row.remaining_amount == Decimal("60.00")
    assert row.past_due_reason_code == "business_slow"
