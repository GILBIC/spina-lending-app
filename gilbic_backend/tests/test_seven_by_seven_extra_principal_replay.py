from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal
from hashlib import sha256
from uuid import UUID

import pytest
from gilbic_backend.seven_by_seven_extra_principal import (
    FutureInstallmentPrincipalState,
)
from gilbic_backend.seven_by_seven_extra_principal_replay import (
    ActiveExtraPrincipalEvent,
    SevenBySevenExtraPrincipalReplayError,
    replay_extra_principal_history,
    require_extra_principal_interest_clear,
)

FIRST_ADJUSTMENT_ID = UUID("74109c8f-91ca-41b9-b04e-b604eed7e7fc")
SECOND_ADJUSTMENT_ID = UUID("91c825c5-b4f3-43e3-9c19-97c8ab96b301")
FIRST_TRANSACTION_ID = UUID("f422c27e-5b2c-4c47-bf33-5642d43c3478")
SECOND_TRANSACTION_ID = UUID("fed39f6c-b0be-42ad-9127-acb4f56f882f")


def _signed_row(number: int) -> FutureInstallmentPrincipalState:
    return FutureInstallmentPrincipalState(
        installment_id=100 + number,
        installment_number=number,
        effective_due_date=date(2026, 9, 1) + timedelta(days=number - 1),
        contractual_amount=Decimal("50.00"),
        principal_component=Decimal("29.00"),
        interest_component=Decimal("21.00"),
    )


def _event(
    adjustment_id: UUID,
    transaction_id: UUID,
    *,
    reduction: str,
    version: int,
) -> ActiveExtraPrincipalEvent:
    return ActiveExtraPrincipalEvent(
        adjustment_id=adjustment_id,
        transaction_id=transaction_id,
        principal_reduction=Decimal(reduction),
        resulting_operational_version=version,
    )


def test_interest_gate_rejects_each_collectible_interest_bucket() -> None:
    for past_due, today in (
        (Decimal("0.01"), Decimal("0.00")),
        (Decimal("0.00"), Decimal("21.00")),
    ):
        with pytest.raises(SevenBySevenExtraPrincipalReplayError) as captured:
            require_extra_principal_interest_clear(
                past_due_interest=past_due,
                today_interest=today,
            )

        assert (
            captured.value.code == "seven_by_seven_extra_principal_interest_outstanding"
        )


def test_interest_gate_accepts_exact_zero_money_values() -> None:
    require_extra_principal_interest_clear(
        past_due_interest=Decimal(0),
        today_interest=Decimal("0.000"),
    )


def test_replay_applies_active_events_to_signed_tail_in_version_order() -> None:
    result = replay_extra_principal_history(
        signed_installments=(_signed_row(3), _signed_row(1), _signed_row(2)),
        active_events=(
            _event(
                SECOND_ADJUSTMENT_ID,
                SECOND_TRANSACTION_ID,
                reduction="5.00",
                version=2,
            ),
            _event(
                FIRST_ADJUSTMENT_ID,
                FIRST_TRANSACTION_ID,
                reduction="40.00",
                version=1,
            ),
        ),
    )

    assert result.active_adjustment_ids == (
        FIRST_ADJUSTMENT_ID,
        SECOND_ADJUSTMENT_ID,
    )
    assert result.future_principal == Decimal("42.00")
    first, boundary, removed = result.operational_rows
    assert first.installment_id == 101
    assert first.operational_amount == Decimal("50.00")
    assert first.operational_principal == Decimal("29.00")
    assert first.signed_amount == Decimal("50.00")
    assert first.removed is False

    assert boundary.installment_id == 102
    assert boundary.operational_amount == Decimal("34.00")
    assert boundary.operational_principal == Decimal("13.00")
    assert boundary.operational_interest == Decimal("21.00")
    assert boundary.signed_principal == Decimal("29.00")
    assert boundary.last_active_adjustment_id == SECOND_ADJUSTMENT_ID
    assert boundary.removed is False

    assert removed.installment_id == 103
    assert removed.operational_amount == Decimal("0.00")
    assert removed.operational_principal == Decimal("0.00")
    assert removed.operational_interest == Decimal("0.00")
    assert removed.last_active_adjustment_id == FIRST_ADJUSTMENT_ID
    assert removed.removed is True


def test_replay_digests_are_stable_for_equivalent_input_order() -> None:
    first = replay_extra_principal_history(
        signed_installments=(_signed_row(1), _signed_row(2), _signed_row(3)),
        active_events=(
            _event(
                FIRST_ADJUSTMENT_ID,
                FIRST_TRANSACTION_ID,
                reduction="40.00",
                version=1,
            ),
        ),
    )
    reordered = replay_extra_principal_history(
        signed_installments=(_signed_row(3), _signed_row(1), _signed_row(2)),
        active_events=(
            _event(
                FIRST_ADJUSTMENT_ID,
                FIRST_TRANSACTION_ID,
                reduction="40.0",
                version=1,
            ),
        ),
    )

    assert first.source_history_digest == reordered.source_history_digest
    assert first.operational_state_digest == reordered.operational_state_digest
    expected_source = {
        "events": [
            {
                "adjustment_id": str(FIRST_ADJUSTMENT_ID),
                "principal_reduction": "40.00",
                "resulting_operational_version": 1,
                "transaction_id": str(FIRST_TRANSACTION_ID),
            }
        ],
        "signed_installments": [
            {
                "effective_due_date": f"2026-09-0{number}",
                "installment_id": 100 + number,
                "installment_number": number,
                "signed_amount": "50.00",
                "signed_interest": "21.00",
                "signed_principal": "29.00",
            }
            for number in (1, 2, 3)
        ],
    }
    expected_operational = {
        "active_adjustment_ids": [str(FIRST_ADJUSTMENT_ID)],
        "installments": [
            {
                "effective_due_date": "2026-09-01",
                "installment_id": 101,
                "installment_number": 1,
                "last_active_adjustment_id": str(FIRST_ADJUSTMENT_ID),
                "operational_amount": "50.00",
                "operational_interest": "21.00",
                "operational_principal": "29.00",
                "removed": False,
                "signed_amount": "50.00",
                "signed_interest": "21.00",
                "signed_principal": "29.00",
            },
            {
                "effective_due_date": "2026-09-02",
                "installment_id": 102,
                "installment_number": 2,
                "last_active_adjustment_id": str(FIRST_ADJUSTMENT_ID),
                "operational_amount": "39.00",
                "operational_interest": "21.00",
                "operational_principal": "18.00",
                "removed": False,
                "signed_amount": "50.00",
                "signed_interest": "21.00",
                "signed_principal": "29.00",
            },
            {
                "effective_due_date": "2026-09-03",
                "installment_id": 103,
                "installment_number": 3,
                "last_active_adjustment_id": str(FIRST_ADJUSTMENT_ID),
                "operational_amount": "0.00",
                "operational_interest": "0.00",
                "operational_principal": "0.00",
                "removed": True,
                "signed_amount": "50.00",
                "signed_interest": "21.00",
                "signed_principal": "29.00",
            },
        ],
    }

    def literal_digest(payload: dict[str, object]) -> str:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        return sha256(encoded).hexdigest()

    assert first.source_history_digest == literal_digest(expected_source)
    assert first.operational_state_digest == literal_digest(expected_operational)


def test_replay_rejects_duplicate_adjustment_identity() -> None:
    duplicate = _event(
        FIRST_ADJUSTMENT_ID,
        SECOND_TRANSACTION_ID,
        reduction="5.00",
        version=2,
    )
    with pytest.raises(SevenBySevenExtraPrincipalReplayError) as captured:
        replay_extra_principal_history(
            signed_installments=(_signed_row(1), _signed_row(2), _signed_row(3)),
            active_events=(
                _event(
                    FIRST_ADJUSTMENT_ID,
                    FIRST_TRANSACTION_ID,
                    reduction="40.00",
                    version=1,
                ),
                duplicate,
            ),
        )

    assert captured.value.code == "seven_by_seven_extra_principal_replay_conflict"


def test_replay_rejects_duplicate_operational_version() -> None:
    with pytest.raises(SevenBySevenExtraPrincipalReplayError) as captured:
        replay_extra_principal_history(
            signed_installments=(_signed_row(1), _signed_row(2), _signed_row(3)),
            active_events=(
                _event(
                    FIRST_ADJUSTMENT_ID,
                    FIRST_TRANSACTION_ID,
                    reduction="20.00",
                    version=1,
                ),
                _event(
                    SECOND_ADJUSTMENT_ID,
                    SECOND_TRANSACTION_ID,
                    reduction="5.00",
                    version=1,
                ),
            ),
        )

    assert captured.value.code == "seven_by_seven_extra_principal_replay_conflict"
