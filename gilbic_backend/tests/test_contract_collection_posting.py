from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from gilbic_backend.collection_correction_repository import CollectionCorrectionInvalid
from gilbic_backend.contract_collection_correction import (
    ContractSafeCollectionCorrectionRepository,
)
from gilbic_backend.contract_collection_posting import (
    CONTRACT_ALLOCATION_SETTING,
    ContractAwareCrossCollectorCollectionPostingBridge,
    ContractCollectionGate,
)
from gilbic_backend.per_loan_contract_collection import (
    PerLoanContractAwareCrossCollectorCollectionPostingBridge,
)
from spina_mobile_collections.contracts import (
    ActorContext,
    CollectionCommand,
    CollectionEntryType,
    PostedCollection,
)
from spina_mobile_collections.service import CollectionRejected


PACKAGE = Path(__file__).resolve().parents[1] / "src" / "gilbic_backend"
COLLECTION_API = (PACKAGE / "collection_api.py").read_text(encoding="utf-8")
SEVEN_BY_SEVEN_COLLECTION = (
    PACKAGE / "seven_by_seven_collection_posting.py"
).read_text(encoding="utf-8")
CORRECTION_API = (PACKAGE / "collection_correction_api.py").read_text(encoding="utf-8")
SCHEDULE_SERVICE = (PACKAGE / "contract_schedule_service.py").read_text(encoding="utf-8")

LOAN_ID = UUID("44444444-4444-4444-8444-444444444444")
CLIENT_ID = UUID("33333333-3333-4333-8333-333333333333")
COLLECTOR_ID = UUID("11111111-1111-4111-8111-111111111111")
DEVICE_ID = UUID("22222222-2222-4222-8222-222222222222")
KEY = UUID("55555555-5555-4555-8555-555555555555")
SCHEDULE_ID = UUID("66666666-6666-4666-8666-666666666666")


def command(
    *,
    entry_type: CollectionEntryType = CollectionEntryType.PAYMENT,
    amount: Decimal | None = Decimal("90.00"),
    covered_dates: tuple[date, ...] = (),
    advance_from: date | None = None,
    advance_until: date | None = None,
) -> CollectionCommand:
    return CollectionCommand(
        idempotency_key=KEY,
        route_entry_id=str(LOAN_ID),
        client_id=str(CLIENT_ID),
        loan_id=str(LOAN_ID),
        collection_date=date(2026, 8, 9),
        entry_type=entry_type,
        amount=amount,
        advance_from=advance_from,
        advance_until=advance_until,
        covered_dates=covered_dates,
        recorded_at=datetime(2026, 8, 9, 2, 0, tzinfo=timezone.utc),
        device_id="test-device",
        device_sequence=1,
        route_revision=f"loan:{LOAN_ID}:v1",
    )


def actor() -> ActorContext:
    return ActorContext(
        account_id=str(COLLECTOR_ID),
        device_id="test-device",
        registered_device_id=str(DEVICE_ID),
        permissions=frozenset({"collection.create"}),
    )


class OneRowCursor:
    def __init__(self, *, row: dict[str, Any] | None = None, rows=()) -> None:
        self.row = row
        self.rows = tuple(rows)
        self.executions: list[tuple[str, tuple[Any, ...] | None]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        return False

    def execute(self, statement: str, parameters: tuple[Any, ...] | None = None):
        self.executions.append((statement, parameters))
        return self

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class OneCursorConnection:
    def __init__(self, cursor: OneRowCursor) -> None:
        self.cursor_instance = cursor

    def cursor(self, **_: Any) -> OneRowCursor:
        return self.cursor_instance


def gate_row(**changes: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "allocation_enabled": True,
        "remaining_balance": Decimal("270.00"),
        "schedule_id": SCHEDULE_ID,
        "schedule_version": 1,
        "payment_frequency": "daily",
        "contract_reference": "SIGNED-001",
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


def per_loan_gate_row(**changes: Any) -> dict[str, Any]:
    row = gate_row()
    row.pop("allocation_enabled")
    row.update(
        {
            "activation_is_active": True,
            "activation_schedule_id": SCHEDULE_ID,
            "mobile_collections_enabled": True,
            "mobile_balance_mode": "direct_remaining_balance",
            "collection_state_reconciled": True,
        }
    )
    row.update(changes)
    return row


def contract_gate() -> ContractCollectionGate:
    return ContractCollectionGate(
        loan_id=LOAN_ID,
        schedule_id=SCHEDULE_ID,
        schedule_version=1,
        payment_frequency="daily",
        contract_reference="SIGNED-001",
        remaining_balance=Decimal("270.00"),
        unpaid_contractual_amount=Decimal("270.00"),
    )


def test_stage5e46b_live_collection_api_preserves_per_loan_contract_bridge() -> None:
    assert "SevenBySevenAwarePerLoanContractCollectionPostingBridge" in COLLECTION_API
    assert (
        "posting_bridge=SevenBySevenAwarePerLoanContractCollectionPostingBridge()"
        in COLLECTION_API
    )
    assert "PerLoanContractAwareCrossCollectorCollectionPostingBridge" in SEVEN_BY_SEVEN_COLLECTION
    assert "class SevenBySevenAwarePerLoanContractCollectionPostingBridge" in SEVEN_BY_SEVEN_COLLECTION


def test_stage5e44_correction_api_uses_contract_safe_repository() -> None:
    assert "ContractSafeCollectionCorrectionRepository" in CORRECTION_API
    assert "return ContractSafeCollectionCorrectionRepository()" in CORRECTION_API


def test_stage5e44_feature_gate_is_dormant_by_default() -> None:
    assert CONTRACT_ALLOCATION_SETTING == "mobile_contract_schedule_allocation_enabled"
    bridge = ContractAwareCrossCollectorCollectionPostingBridge()
    cursor = OneRowCursor(row=gate_row(allocation_enabled=False))
    assert bridge._load_contract_gate(  # noqa: SLF001
        OneCursorConnection(cursor), command=command()
    ) is None


def test_stage5e46b_per_loan_gate_is_off_without_active_event() -> None:
    bridge = PerLoanContractAwareCrossCollectorCollectionPostingBridge()
    cursor = OneRowCursor(row=per_loan_gate_row(activation_is_active=False))
    assert bridge._load_contract_gate(  # noqa: SLF001
        OneCursorConnection(cursor), command=command()
    ) is None


def test_stage5e46b_per_loan_gate_uses_only_current_activated_schedule() -> None:
    bridge = PerLoanContractAwareCrossCollectorCollectionPostingBridge()
    cursor = OneRowCursor(row=per_loan_gate_row())
    gate = bridge._load_contract_gate(  # noqa: SLF001
        OneCursorConnection(cursor), command=command()
    )
    assert gate is not None
    assert gate.loan_id == LOAN_ID
    assert gate.schedule_id == SCHEDULE_ID

    stale = OneRowCursor(
        row=per_loan_gate_row(activation_schedule_id=UUID(int=999))
    )
    with pytest.raises(CollectionRejected) as caught:
        bridge._load_contract_gate(  # noqa: SLF001
            OneCursorConnection(stale), command=command()
        )
    assert caught.value.code == "contract_activation_schedule_changed"


def test_stage5e46b_per_loan_gate_rechecks_operational_mode() -> None:
    bridge = PerLoanContractAwareCrossCollectorCollectionPostingBridge()
    for changes in (
        {"mobile_collections_enabled": False},
        {"mobile_balance_mode": "statement_only"},
    ):
        cursor = OneRowCursor(row=per_loan_gate_row(**changes))
        with pytest.raises(CollectionRejected) as caught:
            bridge._load_contract_gate(  # noqa: SLF001
                OneCursorConnection(cursor), command=command()
            )
        assert caught.value.code == "contract_activation_operational_mode_changed"


def test_stage5e44_normal_payment_does_not_force_collection_date_coverage() -> None:
    bridge = ContractAwareCrossCollectorCollectionPostingBridge()
    bridge._contract_mode = True  # noqa: SLF001
    try:
        assert bridge._covered_dates(command()) == ()  # noqa: SLF001
    finally:
        bridge._contract_mode = False  # noqa: SLF001


def test_stage5e44_advance_keeps_only_exact_contract_dates() -> None:
    selected = (date(2026, 8, 9), date(2026, 8, 16))
    bridge = ContractAwareCrossCollectorCollectionPostingBridge()
    bridge._contract_mode = True  # noqa: SLF001
    try:
        assert bridge._covered_dates(  # noqa: SLF001
            command(
                entry_type=CollectionEntryType.ADVANCE,
                amount=Decimal("180.00"),
                covered_dates=selected,
                advance_from=selected[0],
                advance_until=selected[-1],
            )
        ) == selected
    finally:
        bridge._contract_mode = False  # noqa: SLF001


def test_stage5e44_verified_gate_requires_ready_registered_schedule() -> None:
    bridge = ContractAwareCrossCollectorCollectionPostingBridge()
    missing_registration = OneRowCursor(row=gate_row(registration_id=None))
    with pytest.raises(CollectionRejected) as caught:
        bridge._load_contract_gate(  # noqa: SLF001
            OneCursorConnection(missing_registration), command=command()
        )
    assert caught.value.code == "contract_schedule_not_verified"

    not_ready = OneRowCursor(row=gate_row(dpd_data_status="payment_allocation_required"))
    with pytest.raises(CollectionRejected) as caught:
        bridge._load_contract_gate(  # noqa: SLF001
            OneCursorConnection(not_ready), command=command()
        )
    assert caught.value.code == "contract_schedule_allocation_not_ready"


def test_stage5e44_contract_gate_blocks_operational_balance_mismatch() -> None:
    bridge = ContractAwareCrossCollectorCollectionPostingBridge()
    cursor = OneRowCursor(row=gate_row(remaining_balance=Decimal("180.00")))
    with pytest.raises(CollectionRejected) as caught:
        bridge._load_contract_gate(  # noqa: SLF001
            OneCursorConnection(cursor), command=command()
        )
    assert caught.value.code == "contract_balance_not_reconciled"


def test_stage5e44_contract_gate_keeps_default_ecl_and_posting_off() -> None:
    bridge = ContractAwareCrossCollectorCollectionPostingBridge()
    for changes in (
        {"automatic_default_label_written": True},
        {"ecl_included": True},
        {"ecl_amount": Decimal("1.00")},
        {"ready_to_post": True},
    ):
        cursor = OneRowCursor(row=gate_row(**changes))
        with pytest.raises(CollectionRejected) as caught:
            bridge._load_contract_gate(  # noqa: SLF001
                OneCursorConnection(cursor), command=command()
            )
        assert caught.value.code == "contract_schedule_accounting_guard"


def test_stage5e44_pass_requires_an_actual_unpaid_due_installment_today() -> None:
    bridge = ContractAwareCrossCollectorCollectionPostingBridge()
    cursor = OneRowCursor(row={"has_unpaid_due": False})
    with pytest.raises(CollectionRejected) as caught:
        bridge._verify_contract_pass_due(  # noqa: SLF001
            OneCursorConnection(cursor),
            gate=contract_gate(),
            command=command(entry_type=CollectionEntryType.PASS, amount=None),
        )
    assert caught.value.code == "contract_pass_not_due"


def test_stage5e44_advance_requires_exact_dates_and_full_selected_amount() -> None:
    selected = (date(2026, 8, 9), date(2026, 8, 16))
    rows = (
        {
            "effective_due_date": selected[0],
            "contractual_amount": Decimal("90.00"),
            "allocated_amount": Decimal("0.00"),
        },
        {
            "effective_due_date": selected[1],
            "contractual_amount": Decimal("90.00"),
            "allocated_amount": Decimal("0.00"),
        },
    )
    bridge = ContractAwareCrossCollectorCollectionPostingBridge()
    cursor = OneRowCursor(rows=rows)
    bridge._verify_contract_advance(  # noqa: SLF001
        OneCursorConnection(cursor),
        gate=contract_gate(),
        command=command(
            entry_type=CollectionEntryType.ADVANCE,
            amount=Decimal("180.00"),
            covered_dates=selected,
            advance_from=selected[0],
            advance_until=selected[-1],
        ),
    )

    cursor = OneRowCursor(rows=rows)
    with pytest.raises(CollectionRejected) as caught:
        bridge._verify_contract_advance(  # noqa: SLF001
            OneCursorConnection(cursor),
            gate=contract_gate(),
            command=command(
                entry_type=CollectionEntryType.ADVANCE,
                amount=Decimal("90.00"),
                covered_dates=selected,
                advance_from=selected[0],
                advance_until=selected[-1],
            ),
        )
    assert caught.value.code == "contract_advance_amount_mismatch"


def test_stage5e44_orchestration_keeps_official_and_contract_writes_atomic() -> None:
    events: list[str] = []

    class Harness(ContractAwareCrossCollectorCollectionPostingBridge):
        def _load_contract_gate(self, connection, *, command):
            events.append("gate")
            return contract_gate()

        def _post_official_collection(self, connection, actor, command):
            assert self._contract_mode is True
            events.append("official")
            return PostedCollection(
                server_transaction_id=str(UUID(int=99)),
                receipt_number="TEST-1",
                official_balance=Decimal("180.00"),
                accepted_at=datetime.now(timezone.utc),
            )

        def _finalize_contract_effects(self, connection, *, actor, command, gate, posted):
            assert self._contract_mode is False
            events.append("contract")

    Harness().post_collection(object(), actor(), command())
    assert events == ["gate", "official", "contract"]


def test_stage5e44_voided_allocations_do_not_consume_future_installments() -> None:
    assert "allocation_transaction.is_voided = false" in SCHEDULE_SERVICE
    assert "Allocations belonging to a voided collection" in SCHEDULE_SERVICE


def test_stage5e44_contract_controlled_corrections_require_void_and_repost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ContractSafeCollectionCorrectionRepository,
        "_is_contract_controlled",
        staticmethod(lambda **_: True),
    )
    with pytest.raises(CollectionCorrectionInvalid) as caught:
        ContractSafeCollectionCorrectionRepository().correct_own_unremitted(
            actor_user_id=COLLECTOR_ID,
            transaction_id=UUID(int=100),
            entry_type="payment",
            amount=Decimal("90.00"),
            covered_dates=(date(2026, 8, 9),),
            note="",
            reason="wrong amount",
            expected_route_revision=f"loan:{LOAN_ID}:v1",
        )
    assert "Void the unremitted receipt" in str(caught.value)
