from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from types import TracebackType
from typing import Any, Self
from uuid import UUID

import gilbic_backend.management_dashboard_overview_repository as overview_repository
import pytest
from gilbic_backend.management_dashboard_overview_repository import (
    ManagementDashboardOverviewError,
    PostgresManagementDashboardOverviewRepository,
)

ACTOR_USER_ID = UUID("11111111-1111-4111-8111-111111111111")


class FakeCursor:
    def __init__(self, row: dict[str, Any] | None) -> None:
        self.row = row
        self.execute_count = 0
        self.query = ""
        self.parameters: tuple[object, ...] = ()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def execute(self, query: str, parameters: tuple[object, ...]) -> None:
        self.execute_count += 1
        self.query = query
        self.parameters = parameters

    def fetchone(self) -> dict[str, Any] | None:
        return self.row


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self._cursor = cursor

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def cursor(self, *, row_factory: object) -> FakeCursor:
        assert row_factory is not None
        return self._cursor


def _snapshot_row() -> dict[str, Any]:
    return {
        "generated_at": datetime(2026, 8, 29, 4, 15, 30, tzinfo=timezone.utc),
        "active_client_count": 128,
        "active_loan_count": 142,
        "overdue_loan_count": 9,
        "outstanding_balance": Decimal("987654.32"),
        "latest_collection_date": date(2026, 8, 28),
        "latest_collection_count": 94,
        "latest_collection_amount": Decimal("41250.00"),
        "unremitted_count": 7,
        "unremitted_amount": Decimal("10650.00"),
        "remittance_count": 3,
        "remittance_amount": Decimal("18500.00"),
        "renewal_count": 4,
        "staff_registration_count": 2,
        "client_registration_count": 5,
        "collector_device_count": 1,
        "support_count": 6,
        "unread_activity_count": 8,
    }


def _load(
    monkeypatch: pytest.MonkeyPatch,
    row: dict[str, Any] | None,
    *,
    include_remittances: bool = False,
    include_renewals: bool = True,
    include_accounts: bool = False,
    include_devices: bool = True,
    include_support: bool = False,
):
    cursor = FakeCursor(row)
    monkeypatch.setattr(
        overview_repository,
        "open_connection",
        lambda: FakeConnection(cursor),
    )
    result = PostgresManagementDashboardOverviewRepository().load_overview(
        actor_user_id=ACTOR_USER_ID,
        include_remittances=include_remittances,
        include_renewals=include_renewals,
        include_accounts=include_accounts,
        include_devices=include_devices,
        include_support=include_support,
    )
    return result, cursor


def test_load_overview_uses_one_statement_and_omits_unpermitted_queues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, cursor = _load(monkeypatch, _snapshot_row())

    assert cursor.execute_count == 1
    assert cursor.parameters == (
        False,
        False,
        ACTOR_USER_ID,
        True,
        False,
        False,
        True,
        False,
        ACTOR_USER_ID,
    )
    assert [metric.key for metric in result.metrics] == [
        "portfolio.active_clients",
        "portfolio.active_loans",
        "portfolio.overdue_loans",
        "portfolio.outstanding_balance",
        "collections.latest_day",
        "collections.unremitted",
        "queues.renewals_protected",
        "queues.collector_mobile_devices",
        "activity.unread",
    ]
    assert "statement_timestamp()" in cursor.query
    assert "recipient_user_id = %s" in cursor.query
    assert "collection_remittance_rejections" in cursor.query
    assert "request.status in ('open', 'answered')" in cursor.query


def test_load_overview_returns_all_authorized_metrics_in_contract_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, _ = _load(
        monkeypatch,
        _snapshot_row(),
        include_remittances=True,
        include_renewals=True,
        include_accounts=True,
        include_devices=True,
        include_support=True,
    )

    assert result.generated_at == datetime(
        2026,
        8,
        29,
        4,
        15,
        30,
        tzinfo=timezone.utc,
    )
    assert [metric.key for metric in result.metrics] == [
        "portfolio.active_clients",
        "portfolio.active_loans",
        "portfolio.overdue_loans",
        "portfolio.outstanding_balance",
        "collections.latest_day",
        "collections.unremitted",
        "queues.remittances_assigned",
        "queues.renewals_protected",
        "queues.staff_registrations",
        "queues.client_registrations",
        "queues.collector_mobile_devices",
        "queues.borrower_support",
        "activity.unread",
    ]
    by_key = {metric.key: metric for metric in result.metrics}
    assert by_key["portfolio.outstanding_balance"].amount == Decimal("987654.32")
    assert by_key["collections.latest_day"].as_of_date == date(2026, 8, 28)
    assert by_key["queues.remittances_assigned"].count == 3
    assert by_key["queues.remittances_assigned"].amount == Decimal("18500.00")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("active_client_count", -1),
        ("outstanding_balance", Decimal("-0.01")),
        ("unread_activity_count", True),
        ("latest_collection_amount", "41250.00"),
        (
            "generated_at",
            datetime(2026, 8, 29, 4, 15, 30, tzinfo=timezone.utc).replace(tzinfo=None),
        ),
    ],
)
def test_load_overview_rejects_invalid_authoritative_values(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
) -> None:
    row = _snapshot_row()
    row[field] = value

    with pytest.raises(ManagementDashboardOverviewError) as captured:
        _load(
            monkeypatch,
            row,
            include_remittances=True,
            include_accounts=True,
            include_support=True,
        )

    assert str(captured.value) == "The Management overview data is invalid."


def test_load_overview_rejects_a_missing_database_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ManagementDashboardOverviewError) as captured:
        _load(monkeypatch, None)

    assert str(captured.value) == "The Management overview data is unavailable."
