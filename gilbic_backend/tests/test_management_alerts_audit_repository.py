from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from types import TracebackType
from typing import Any, Self
from uuid import UUID

import gilbic_backend.management_alerts_audit_repository as repository_module
import pytest
from gilbic_backend.management_alerts_audit_repository import (
    PROTECTED_FINANCIAL_SOURCE_TYPES,
    ManagementAlertsAuditError,
    PostgresManagementAlertsAuditRepository,
)

ACTOR_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
RECORD_ID = UUID("22222222-2222-4222-8222-222222222222")


class FakeCursor:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
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

    def fetchall(self) -> list[dict[str, Any]]:
        return self.rows


class FakeConnection:
    def __init__(self, cursor: FakeCursor) -> None:
        self.cursor_value = cursor

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
        return self.cursor_value


def _base_row() -> dict[str, Any]:
    return {
        "generated_at": datetime(2026, 8, 30, 3, 5, tzinfo=timezone.utc),
        "payment_updates_unread_count": 4,
        "assigned_remittance_count": 3,
        "assigned_remittance_amount": Decimal("1450.00"),
        "unresolved_rejected_remittance_count": 1,
        "pending_renewal_count": 2,
        "pending_staff_registration_count": 1,
        "pending_client_registration_count": 5,
        "pending_staff_device_count": 2,
        "pending_support_count": 6,
        "protected_financial_audit_gap_count": 1,
        "event_key": "financial:91",
        "action_code": "financial.posted",
        "occurred_at": datetime(2026, 8, 30, 3, 0, tzinfo=timezone.utc),
        "business_date": date(2026, 8, 30),
        "record_id": RECORD_ID,
        "reference": "GJ-2026-00000091",
        "current_state": "posted",
        "actor_name": "Accounting Manager",
        "checker_name": "Accounting Manager",
        "source_type": "v1_tax_recoverable_refund",
        "reason": None,
        "event_total_count": 1,
    }


def _load(
    monkeypatch: pytest.MonkeyPatch,
    rows: list[dict[str, Any]],
    **overrides: object,
):
    cursor = FakeCursor(rows)
    monkeypatch.setattr(
        repository_module,
        "open_connection",
        lambda: FakeConnection(cursor),
    )
    arguments: dict[str, object] = {
        "actor_user_id": ACTOR_USER_ID,
        "include_accounts": True,
        "include_devices": True,
        "include_renewals": True,
        "include_support": True,
        "include_remittances": True,
        "include_financial": True,
        "window_days": 30,
        "limit": 100,
    }
    arguments.update(overrides)
    snapshot = PostgresManagementAlertsAuditRepository().load_snapshot(**arguments)
    return snapshot, cursor


def test_projection_uses_one_statement_and_only_reviewed_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot, cursor = _load(monkeypatch, [_base_row()])

    assert cursor.execute_count == 1
    assert cursor.parameters == (
        ACTOR_USER_ID,
        True,
        True,
        True,
        True,
        True,
        True,
        30,
        100,
        list(PROTECTED_FINANCIAL_SOURCE_TYPES),
    )
    query = " ".join(cursor.query.lower().split())
    assert "statement_timestamp()" in query
    assert "collection_remittance_rejections" in query
    assert "accounting.journal_events" in query
    assert "accounting.journal_entries" in query
    assert "core.client_registration_requests" in query
    assert "core.devices" in query
    assert "client_renewal_requests" in query
    assert "client_support_requests" in query
    assert "audit.details" not in query
    assert "recipient_user_id = settings.actor_user_id" in query
    assert "journal.source_type = any(settings.protected_source_types)" in query
    assert snapshot.event_total_count == 1
    assert snapshot.events[0].source_label == "Tax Recoverable refund"
    assert [alert.code for alert in snapshot.alerts] == [
        "payment_updates_unread",
        "assigned_remittances",
        "unresolved_rejected_remittances",
        "renewal_requests",
        "staff_registrations",
        "client_registrations",
        "staff_devices",
        "support_requests",
        "protected_financial_audit_gaps",
    ]


def test_permission_reduction_omits_unavailable_alerts_and_domains(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot, _ = _load(
        monkeypatch,
        [_base_row()],
        include_accounts=False,
        include_devices=False,
        include_renewals=False,
        include_support=False,
        include_remittances=False,
        include_financial=False,
    )

    assert snapshot.visible_domains == ("payment_updates",)
    assert [alert.code for alert in snapshot.alerts] == [
        "payment_updates_unread",
    ]
    # A permission-filtered SQL result must not leak an event from a disabled domain.
    assert snapshot.events == ()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("payment_updates_unread_count", -1),
        ("assigned_remittance_amount", Decimal("-0.01")),
        ("event_total_count", True),
        ("generated_at", datetime(2026, 8, 30, 3, 5)),  # noqa: DTZ001
        ("action_code", "financial.unknown"),
        ("source_type", "unreviewed_source"),
    ],
)
def test_projection_rejects_invalid_or_unreviewed_data(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
) -> None:
    row = _base_row()
    row[field] = value

    with pytest.raises(ManagementAlertsAuditError):
        _load(monkeypatch, [row])


def test_empty_event_page_still_returns_authoritative_alerts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = _base_row()
    row.update(
        {
            "event_key": None,
            "action_code": None,
            "occurred_at": None,
            "business_date": None,
            "record_id": None,
            "reference": None,
            "current_state": None,
            "actor_name": None,
            "checker_name": None,
            "source_type": None,
            "reason": None,
            "event_total_count": 0,
        }
    )

    snapshot, _ = _load(monkeypatch, [row])

    assert snapshot.events == ()
    assert snapshot.event_total_count == 0
    assert snapshot.alerts


def test_missing_projection_row_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ManagementAlertsAuditError):
        _load(monkeypatch, [])
