from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest

from gilbic_backend.per_loan_contract_collection import (
    PerLoanContractAwareCrossCollectorCollectionPostingBridge,
)
from spina_mobile_collections.contracts import CollectionCommand, CollectionEntryType
from spina_mobile_collections.service import CollectionConflict, CollectionRejected


LOAN_ID = UUID("44444444-4444-4444-8444-444444444444")
CLIENT_ID = UUID("33333333-3333-4333-8333-333333333333")
SCHEDULE_ID = UUID("66666666-6666-4666-8666-666666666666")


class _Cursor:
    def __init__(self, row: dict[str, Any]) -> None:
        self.row = row
        self.statements: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        return False

    def execute(self, statement, parameters=None):
        self.statements.append(str(statement))
        return self

    def fetchone(self):
        return self.row


class _Connection:
    def __init__(self, row: dict[str, Any]) -> None:
        self._cursor = _Cursor(row)

    def cursor(self, **kwargs):
        return self._cursor


def _command() -> CollectionCommand:
    return CollectionCommand(
        idempotency_key=UUID("55555555-5555-4555-8555-555555555555"),
        route_entry_id=str(LOAN_ID),
        client_id=str(CLIENT_ID),
        loan_id=str(LOAN_ID),
        collection_date=date(2026, 8, 9),
        entry_type=CollectionEntryType.PAYMENT,
        amount=Decimal("90.00"),
        recorded_at=datetime(2026, 8, 9, 2, 0, tzinfo=timezone.utc),
        device_id="synthetic-device",
        device_sequence=1,
        route_revision=f"loan:{LOAN_ID}:v1",
    )


def _row(**changes: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "activation_action": "activate",
        "activation_is_active": True,
        "activation_schedule_id": SCHEDULE_ID,
        "mobile_collections_enabled": True,
        "mobile_balance_mode": "direct_remaining_balance",
        "remaining_balance": Decimal("270.00"),
        "collection_state_reconciled": True,
        "schedule_id": SCHEDULE_ID,
        "schedule_version": 1,
        "payment_frequency": "daily",
        "contract_reference": "SYNTH-SIGNED-001",
        "dpd_data_status": "ready",
        "contractual_schedule_total": Decimal("270.00"),
        "allocated_schedule_total": Decimal("0.00"),
        "automatic_default_label_written": False,
        "ecl_included": False,
        "ecl_amount": None,
        "ready_to_post": False,
        "registration_id": 1,
    }
    row.update(changes)
    return row


def _locked_activation_row(**changes: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "activation_action": "activate",
        "activation_schedule_id": SCHEDULE_ID,
        "current_schedule_id": SCHEDULE_ID,
        "registration_id": 1,
    }
    row.update(changes)
    return row


def test_never_activated_loan_stays_on_existing_official_path() -> None:
    bridge = PerLoanContractAwareCrossCollectorCollectionPostingBridge()
    assert bridge._load_contract_gate(  # noqa: SLF001
        _Connection(_row(activation_action="", activation_is_active=False)),
        command=_command(),
    ) is None


def test_explicitly_deactivated_contract_loan_cannot_fall_back_to_legacy_mobile_path() -> None:
    bridge = PerLoanContractAwareCrossCollectorCollectionPostingBridge()
    with pytest.raises(CollectionRejected) as caught:
        bridge._load_contract_gate(  # noqa: SLF001
            _Connection(_row(activation_action="deactivate", activation_is_active=False)),
            command=_command(),
        )
    assert caught.value.code == "contract_collection_deactivated"


def test_unreconciled_official_state_blocks_contract_gate_even_if_balances_match() -> None:
    bridge = PerLoanContractAwareCrossCollectorCollectionPostingBridge()
    with pytest.raises(CollectionRejected) as caught:
        bridge._load_contract_gate(  # noqa: SLF001
            _Connection(_row(collection_state_reconciled=False)),
            command=_command(),
        )
    assert caught.value.code == "loan_state_not_reconciled"


def test_stale_active_schedule_is_blocked_instead_of_falling_back() -> None:
    bridge = PerLoanContractAwareCrossCollectorCollectionPostingBridge()
    with pytest.raises(CollectionRejected) as caught:
        bridge._load_contract_gate(  # noqa: SLF001
            _Connection(_row(activation_schedule_id=UUID(int=999))),
            command=_command(),
        )
    assert caught.value.code == "contract_activation_schedule_changed"


def test_activation_is_rechecked_after_loan_lock_and_deactivation_wins() -> None:
    cursor = _Cursor(_locked_activation_row(activation_action="deactivate"))
    bridge = PerLoanContractAwareCrossCollectorCollectionPostingBridge()
    with pytest.raises(CollectionConflict) as caught:
        bridge._verify_activation_after_loan_lock(  # noqa: SLF001
            cursor,
            loan_id=LOAN_ID,
        )
    assert caught.value.code == "contract_activation_changed"
    assert any("loan_contract_collection_activation_state" in sql for sql in cursor.statements)


def test_locked_activation_must_still_match_current_verified_schedule() -> None:
    cursor = _Cursor(
        _locked_activation_row(current_schedule_id=UUID(int=999))
    )
    bridge = PerLoanContractAwareCrossCollectorCollectionPostingBridge()
    with pytest.raises(CollectionConflict) as caught:
        bridge._verify_activation_after_loan_lock(  # noqa: SLF001
            cursor,
            loan_id=LOAN_ID,
        )
    assert caught.value.code == "contract_activation_schedule_changed"


def test_locked_current_activation_is_accepted() -> None:
    cursor = _Cursor(_locked_activation_row())
    bridge = PerLoanContractAwareCrossCollectorCollectionPostingBridge()
    bridge._verify_activation_after_loan_lock(  # noqa: SLF001
        cursor,
        loan_id=LOAN_ID,
    )
