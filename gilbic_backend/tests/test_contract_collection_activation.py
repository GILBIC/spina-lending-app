from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from gilbic_backend.contract_collection_activation_repository import (
    ContractCollectionActivationPreview,
)


PACKAGE = Path(__file__).resolve().parents[1] / "src" / "gilbic_backend"
API_SOURCE = (PACKAGE / "contract_collection_activation_api.py").read_text(
    encoding="utf-8"
)
REPOSITORY_SOURCE = (
    PACKAGE / "contract_collection_activation_repository.py"
).read_text(encoding="utf-8")
MAIN_SOURCE = (PACKAGE / "main.py").read_text(encoding="utf-8")
ROUTE_API_SOURCE = (PACKAGE / "collector_route_api.py").read_text(encoding="utf-8")
SEVEN_BY_SEVEN_ROUTE_SOURCE = (
    PACKAGE / "seven_by_seven_collector_route.py"
).read_text(encoding="utf-8")

LOAN_ID = UUID("44444444-4444-4444-8444-444444444444")
SCHEDULE_ID = UUID("66666666-6666-4666-8666-666666666666")
USER_ID = UUID("11111111-1111-4111-8111-111111111111")


def preview(**changes):
    values = dict(
        loan_id=LOAN_ID,
        loan_number="LN-001",
        client_name="Synthetic Client",
        loan_type_name="Regular",
        loan_status="active",
        remaining_balance=Decimal("270.00"),
        collection_state_reconciled=True,
        mobile_collections_enabled=True,
        mobile_balance_mode="direct_remaining_balance",
        schedule_id=SCHEDULE_ID,
        schedule_version=1,
        payment_frequency="daily",
        contract_reference="SIGNED-001",
        dpd_data_status="ready",
        contractual_schedule_total=Decimal("270.00"),
        allocated_schedule_total=Decimal("0.00"),
        registration_id=1,
        automatic_default_label_written=False,
        ecl_included=False,
        ecl_amount=None,
        ready_to_post=False,
        activation_event_id=None,
        activation_action="",
        activation_schedule_id=None,
        activation_note="",
        activated_by_user_id=None,
        activation_acted_at=None,
    )
    values.update(changes)
    return ContractCollectionActivationPreview(**values)


def test_stage5e46b_ready_verified_reconciled_loan_can_activate() -> None:
    item = preview()
    assert item.schedule_verified is True
    assert item.balance_reconciled is True
    assert item.accounting_safe is True
    assert item.blockers == ()
    assert item.can_activate is True
    assert item.can_deactivate is False


def test_stage5e46b_activation_is_blocked_by_each_protected_readiness_gate() -> None:
    cases = (
        preview(collection_state_reconciled=False),
        preview(mobile_collections_enabled=False),
        preview(mobile_balance_mode="statement_only"),
        preview(schedule_id=None, registration_id=None, dpd_data_status="contract_schedule_required"),
        preview(registration_id=None),
        preview(dpd_data_status="payment_allocation_required"),
        preview(remaining_balance=Decimal("180.00")),
        preview(automatic_default_label_written=True),
        preview(ecl_included=True),
        preview(ecl_amount=Decimal("1.00")),
        preview(ready_to_post=True),
    )
    for item in cases:
        assert item.can_activate is False
        assert item.blockers


def test_stage5e46b_official_reconciliation_is_not_replaced_by_balance_coincidence() -> None:
    item = preview(
        collection_state_reconciled=False,
        remaining_balance=Decimal("270.00"),
        contractual_schedule_total=Decimal("270.00"),
        allocated_schedule_total=Decimal("0.00"),
    )
    assert item.balance_reconciled is False
    assert item.can_activate is False
    assert any("Official loan collection state" in blocker for blocker in item.blockers)


def test_stage5e46b_active_state_is_per_loan_and_schedule_specific() -> None:
    active = preview(
        activation_event_id=10,
        activation_action="activate",
        activation_schedule_id=SCHEDULE_ID,
        activation_note="Management approved synthetic activation.",
        activated_by_user_id=USER_ID,
        activation_acted_at=datetime(2026, 8, 9, tzinfo=timezone.utc),
    )
    assert active.is_active is True
    assert active.active_for_current_schedule is True
    assert active.can_activate is False
    assert active.can_deactivate is True

    stale = preview(
        activation_event_id=11,
        activation_action="activate",
        activation_schedule_id=UUID(int=999),
        activation_note="Old schedule activation.",
        activated_by_user_id=USER_ID,
        activation_acted_at=datetime(2026, 8, 9, tzinfo=timezone.utc),
    )
    assert stale.is_active is True
    assert stale.active_for_current_schedule is False
    assert any("older schedule" in blocker for blocker in stale.blockers)


def test_stage5e46b_api_requires_permission_and_explicit_confirmation() -> None:
    assert "lending.contract_collection.activate" in API_SOURCE
    assert "confirm_action" in API_SOURCE
    assert "activation_confirmation_required" in API_SOURCE
    assert "deactivation_confirmation_required" in API_SOURCE
    assert "No loan is activated automatically" in API_SOURCE


def test_stage5e46b_activation_repository_is_append_only_and_never_writes_business_state() -> None:
    assert "loan_contract_collection_activation_events" in REPOSITORY_SOURCE
    assert "event_action" in REPOSITORY_SOURCE
    assert "insert into lending.loan_contract_collection_activation_events" in REPOSITORY_SOURCE
    assert "state.is_reconciled" in REPOSITORY_SOURCE
    forbidden_writes = (
        "update lending.loans",
        "update lending.loan_collection_state",
        "insert into accounting.journal",
        "insert into accounting.general",
        "default_label =",
        "ecl_amount =",
    )
    lowered = REPOSITORY_SOURCE.lower()
    for text in forbidden_writes:
        assert text not in lowered


def test_stage5e46b_router_and_collector_route_preserve_per_loan_activation() -> None:
    assert "create_contract_collection_activation_router" in MAIN_SOURCE
    assert "SevenBySevenGatedPostgresCollectorRouteRepository" in ROUTE_API_SOURCE
    assert "return SevenBySevenGatedPostgresCollectorRouteRepository()" in ROUTE_API_SOURCE
    assert "PerLoanPostgresCollectorRouteRepository" in SEVEN_BY_SEVEN_ROUTE_SOURCE
    assert "class SevenBySevenGatedPostgresCollectorRouteRepository" in SEVEN_BY_SEVEN_ROUTE_SOURCE
