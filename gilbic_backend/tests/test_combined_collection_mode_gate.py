from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from gilbic_backend.combined_collection_api import (
    CombinedExtraAllocationChoice,
    CombinedPaymentLeg,
    CombinedPaymentRequest,
    _collectible_obligation,
    _plan_combined_allocation,
    _validate_regular_plus_7x7,
)
from spina_mobile_collections.service import CollectionRejected

CLIENT_ID = UUID("11111111-1111-4111-8111-111111111111")
REGULAR_LOAN_ID = UUID("22222222-2222-4222-8222-222222222222")
SEVEN_LOAN_ID = UUID("33333333-3333-4333-8333-333333333333")


class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, *_args, **_kwargs):
        return self

    def fetchall(self):
        return self._rows


class _Connection:
    def __init__(self, rows):
        self._rows = rows

    def cursor(self, **_kwargs):
        return _Cursor(self._rows)


class _SingleRowCursor:
    def __init__(self, row):
        self._row = row
        self.executed_sql = ""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql, *_args, **_kwargs):
        self.executed_sql = " ".join(sql.split())
        return self

    def fetchone(self):
        return self._row


class _SingleRowConnection:
    def __init__(self, row):
        self.cursor_instance = _SingleRowCursor(row)

    def cursor(self, **_kwargs):
        return self.cursor_instance


def _body() -> CombinedPaymentRequest:
    return CombinedPaymentRequest(
        client_transaction_id=UUID("44444444-4444-4444-8444-444444444444"),
        client_id=CLIENT_ID,
        collection_date=date(2026, 8, 23),
        recorded_at=datetime(2026, 8, 23, 1, 0, tzinfo=UTC),
        device_id="collector-phone",
        device_sequence=1,
        cash_received_amount=Decimal("235.00"),
        legs=[
            CombinedPaymentLeg(
                route_entry_id=REGULAR_LOAN_ID,
                loan_id=REGULAR_LOAN_ID,
                route_revision=f"loan:{REGULAR_LOAN_ID}:v1",
            ),
            CombinedPaymentLeg(
                route_entry_id=SEVEN_LOAN_ID,
                loan_id=SEVEN_LOAN_ID,
                route_revision=f"loan:{SEVEN_LOAN_ID}:v1",
            ),
        ],
    )


def _rows(first_mode: str, second_mode: str):
    def row(loan_id: UUID, mode: str) -> dict[str, object]:
        settings: dict[str, object] = {
            "mobile_collections_enabled": True,
            "mobile_balance_mode": "direct_remaining_balance",
        }
        if mode == "seven_by_seven":
            settings["mobile_seven_by_seven_enabled"] = True
        return {
            "id": loan_id,
            "client_id": CLIENT_ID,
            "status": "active",
            "client_status": "active",
            "calculation_mode": mode,
            "settings": settings,
            "is_reconciled": True,
            "state_version": 1,
            "remaining_balance": Decimal("5000.00"),
            "principal": Decimal("5000.00"),
            "daily_amount": Decimal("50.00"),
            "date_released": date(2026, 8, 22),
            "daily_interest_per_1000": Decimal("7.00"),
        }

    return [row(REGULAR_LOAN_ID, first_mode), row(SEVEN_LOAN_ID, second_mode)]


def test_exact_fixed_daily_plus_7x7_is_allowed() -> None:
    _validate_regular_plus_7x7(
        _Connection(_rows("fixed_daily", "seven_by_seven")),
        _body(),
        collector_account_id=CLIENT_ID,
    )


def test_custom_plus_7x7_fails_closed() -> None:
    with pytest.raises(CollectionRejected) as caught:
        _validate_regular_plus_7x7(
            _Connection(_rows("custom", "seven_by_seven")),
            _body(),
            collector_account_id=CLIENT_ID,
        )

    assert caught.value.code == "combined_regular_7x7_required"


def test_two_non_7x7_loans_fail_closed() -> None:
    with pytest.raises(CollectionRejected) as caught:
        _validate_regular_plus_7x7(
            _Connection(_rows("fixed_daily", "custom")),
            _body(),
            collector_account_id=CLIENT_ID,
        )

    assert caught.value.code == "combined_regular_7x7_required"


def test_exact_cash_uses_server_authoritative_7x7_then_regular_split() -> None:
    plan = _plan_combined_allocation(
        cash_received=Decimal("150.00"),
        seven_by_seven_collectible=Decimal("50.00"),
        regular_collectible=Decimal("100.00"),
    )

    assert plan.status == "exact"
    assert plan.seven_by_seven_scheduled == Decimal("50.00")
    assert plan.regular_scheduled == Decimal("100.00")
    assert plan.extra_amount == Decimal("0.00")
    assert plan.requires_review is False


def test_active_schedule_without_due_installments_does_not_fall_back_to_daily() -> None:
    connection = _SingleRowConnection(
        {
            "schedule_count": 1,
            "registration_count": 1,
            "installment_count": 0,
            "collectible_amount": Decimal("0.00"),
        }
    )
    collectible, basis = _collectible_obligation(
        connection,
        loan={
            "id": REGULAR_LOAN_ID,
            "calculation_mode": "seven_by_seven",
            "daily_amount": Decimal("50.00"),
            "remaining_balance": Decimal("5000.00"),
        },
        collection_date=date(2026, 8, 23),
    )

    assert collectible == Decimal("0.00")
    assert basis == "verified_schedule"
    assert "left join lending.loan_contract_installments_operational" in (
        connection.cursor_instance.executed_sql
    )


def test_registered_schedule_history_without_one_active_schedule_fails_closed() -> None:
    connection = _SingleRowConnection(
        {
            "schedule_id": None,
            "schedule_count": 0,
            "registration_count": 1,
            "installment_count": 0,
            "collectible_amount": Decimal("0.00"),
        }
    )

    with pytest.raises(CollectionRejected) as caught:
        _collectible_obligation(
            connection,
            loan={
                "id": SEVEN_LOAN_ID,
                "calculation_mode": "seven_by_seven",
                "daily_amount": Decimal("50.00"),
                "remaining_balance": Decimal("5000.00"),
            },
            collection_date=date(2026, 8, 23),
        )

    assert caught.value.code == "combined_active_schedule_required"


def test_prior_exact_two_leg_contract_is_normalized_to_one_untrusted_total() -> None:
    body = _body()
    payload = body.model_dump(mode="json")
    del payload["cash_received_amount"]
    payload["legs"][0]["amount"] = "1.00"
    payload["legs"][1]["amount"] = "234.00"

    normalized = CombinedPaymentRequest.model_validate(payload)

    assert normalized.cash_received_amount == Decimal("235.00")
    assert [leg.legacy_amount for leg in normalized.legs] == [
        Decimal("1.00"),
        Decimal("234.00"),
    ]


@pytest.mark.parametrize(
    ("cash", "expected_seven", "expected_regular"),
    [
        (Decimal("30.00"), Decimal("30.00"), Decimal("0.00")),
        (Decimal("80.00"), Decimal("50.00"), Decimal("30.00")),
    ],
)
def test_short_cash_clears_7x7_before_regular_and_requires_review(
    cash: Decimal,
    expected_seven: Decimal,
    expected_regular: Decimal,
) -> None:
    plan = _plan_combined_allocation(
        cash_received=cash,
        seven_by_seven_collectible=Decimal("50.00"),
        regular_collectible=Decimal("100.00"),
    )

    assert plan.status == "short"
    assert plan.seven_by_seven_scheduled == expected_seven
    assert plan.regular_scheduled == expected_regular
    assert plan.requires_review is True


def test_excess_cash_stays_unallocated_until_borrower_choice() -> None:
    plan = _plan_combined_allocation(
        cash_received=Decimal("170.00"),
        seven_by_seven_collectible=Decimal("50.00"),
        regular_collectible=Decimal("100.00"),
    )

    assert plan.status == "extra_choice_required"
    assert plan.extra_amount == Decimal("20.00")
    assert plan.extra_choice is None
    assert plan.requires_review is True


@pytest.mark.parametrize(
    "choice",
    list(CombinedExtraAllocationChoice),
)
def test_excess_cash_preserves_one_of_four_borrower_directions(
    choice: CombinedExtraAllocationChoice,
) -> None:
    plan = _plan_combined_allocation(
        cash_received=Decimal("170.00"),
        seven_by_seven_collectible=Decimal("50.00"),
        regular_collectible=Decimal("100.00"),
        extra_choice=choice,
    )

    assert plan.status == "excess"
    assert plan.extra_amount == Decimal("20.00")
    assert plan.extra_choice is choice
    assert plan.requires_review is True
