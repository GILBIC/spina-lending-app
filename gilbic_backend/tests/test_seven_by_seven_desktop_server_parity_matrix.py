from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Mapping, Sequence

import pytest

from gilbic_backend.seven_by_seven_operational_allocator import (
    SevenBySevenCashEvent,
    allocate_seven_by_seven_payments,
)
from spina_app.calculation_rules import allocate_x7_payments


MONEY = Decimal("0.01")
DESKTOP_DAILY_INTEREST_PER_1000 = Decimal("7.00")


@dataclass(frozen=True, slots=True)
class ParityCase:
    name: str
    principal: Decimal
    payment_start: date
    payments: tuple[Mapping[str, Any], ...]


def _money(value: Any) -> Decimal:
    return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)


def _event_id(index: int, payment: Mapping[str, Any]) -> str:
    explicit = str(payment.get("event_id") or "").strip()
    return explicit or f"synthetic-{index}"


def _effective_server_events(
    payments: Sequence[Mapping[str, Any]],
    *,
    payment_start: date,
    as_of_date: date,
) -> tuple[SevenBySevenCashEvent, ...]:
    """Apply the Desktop one-effective-positive-payment-per-date input boundary.

    The Desktop helper ignores non-positive/out-of-window rows and lets the latest
    positive row for a calendar date win. The production server allocator itself
    deliberately accepts only canonical, strictly chronological events and fails
    closed on duplicate dates. This test adapter therefore models the already-
    protected source normalization boundary rather than weakening the allocator.
    """

    by_date: dict[date, tuple[int, Mapping[str, Any]]] = {}
    for index, payment in enumerate(payments, start=1):
        payment_date = payment.get("date")
        amount = _money(payment.get("payment", payment.get("amount", 0)))
        if not isinstance(payment_date, date):
            continue
        if amount <= Decimal("0.00"):
            continue
        if payment_date < payment_start or payment_date > as_of_date:
            continue
        by_date[payment_date] = (index, payment)

    return tuple(
        SevenBySevenCashEvent(
            event_id=_event_id(index, payment),
            collection_date=payment_date,
            amount=_money(payment.get("payment", payment.get("amount", 0))),
        )
        for payment_date, (index, payment) in sorted(by_date.items())
    )


def _assert_case_parity(case: ParityCase) -> None:
    assert case.payments, f"{case.name} must have at least one synthetic payment"
    payment_dates = [
        payment["date"]
        for payment in case.payments
        if isinstance(payment.get("date"), date)
        and _money(payment.get("payment", payment.get("amount", 0))) > Decimal("0.00")
        and payment["date"] >= case.payment_start
    ]
    assert payment_dates, f"{case.name} must have one effective payment on/after start"
    as_of_date = max(payment_dates)

    desktop = allocate_x7_payments(
        principal=case.principal,
        payment_start=case.payment_start,
        payments=case.payments,
        as_of_date=as_of_date,
    )
    events = _effective_server_events(
        case.payments,
        payment_start=case.payment_start,
        as_of_date=as_of_date,
    )
    server = allocate_seven_by_seven_payments(
        original_principal=case.principal,
        daily_interest_per_1000=DESKTOP_DAILY_INTEREST_PER_1000,
        payment_start=case.payment_start,
        events=events,
    )

    desktop_unallocated = _money(
        _money(desktop["total_collected"])
        - _money(desktop["interest_paid"])
        - _money(desktop["principal_paid"])
    )

    assert server.fixed_daily_interest == _money(desktop["daily_interest"]), case.name
    assert server.total_interest_paid == _money(desktop["interest_paid"]), case.name
    assert server.total_principal_paid == _money(desktop["principal_paid"]), case.name
    assert server.closing_remaining_principal == _money(
        desktop["remaining_principal"]
    ), case.name
    assert server.closing_interest_arrears == _money(desktop["interest_arrears"]), case.name
    assert server.total_unallocated_cash == desktop_unallocated, case.name
    assert server.complete is (
        _money(desktop["remaining_principal"]) == Decimal("0.00")
        and _money(desktop["interest_arrears"]) == Decimal("0.00")
    ), case.name


PARITY_CASES = (
    ParityCase(
        name="normal_daily_payments",
        principal=Decimal("5000.00"),
        payment_start=date(2026, 8, 1),
        payments=(
            {"event_id": "normal-1", "date": date(2026, 8, 1), "payment": "200.00"},
            {"event_id": "normal-2", "date": date(2026, 8, 2), "payment": "200.00"},
            {"event_id": "normal-3", "date": date(2026, 8, 3), "payment": "200.00"},
        ),
    ),
    ParityCase(
        name="partial_payments_and_interest_arrears",
        principal=Decimal("5000.00"),
        payment_start=date(2026, 8, 1),
        payments=(
            {"event_id": "partial-1", "date": date(2026, 8, 1), "payment": "20.00"},
            {"event_id": "partial-2", "date": date(2026, 8, 2), "payment": "40.00"},
            {"event_id": "partial-3", "date": date(2026, 8, 3), "payment": "100.00"},
        ),
    ),
    ParityCase(
        name="overpayment_is_not_principal_beyond_original_balance",
        principal=Decimal("5000.00"),
        payment_start=date(2026, 8, 1),
        payments=(
            {"event_id": "overpay", "date": date(2026, 8, 1), "payment": "6000.00"},
        ),
    ),
    ParityCase(
        name="pass_equivalent_days_are_calendar_gap_not_cash",
        principal=Decimal("5000.00"),
        payment_start=date(2026, 8, 1),
        payments=(
            {"event_id": "before-pass-gap", "date": date(2026, 8, 1), "payment": "35.00"},
            # Aug 2-4 contain no positive cash event: PASS-equivalent operational days.
            {"event_id": "after-pass-gap", "date": date(2026, 8, 5), "payment": "140.00"},
        ),
    ),
    ParityCase(
        name="advance_exact_covered_dates_do_not_change_cash_allocation_basis",
        principal=Decimal("5000.00"),
        payment_start=date(2026, 8, 1),
        payments=(
            {
                "event_id": "adv-1",
                "date": date(2026, 8, 1),
                "payment": "210.00",
                "entry_type": "advance",
                "covered_dates": (
                    date(2026, 8, 1),
                    date(2026, 8, 2),
                    date(2026, 8, 3),
                ),
            },
            {
                "event_id": "after-adv",
                "date": date(2026, 8, 4),
                "payment": "105.00",
                "entry_type": "payment",
            },
        ),
    ),
    ParityCase(
        name="exact_payoff",
        principal=Decimal("5000.00"),
        payment_start=date(2026, 8, 1),
        payments=(
            {"event_id": "payoff", "date": date(2026, 8, 1), "payment": "5035.00"},
        ),
    ),
    ParityCase(
        name="started_thousand_principal_basis",
        principal=Decimal("5000.01"),
        payment_start=date(2026, 8, 1),
        payments=(
            {"event_id": "started-thousand", "date": date(2026, 8, 1), "payment": "42.00"},
        ),
    ),
    ParityCase(
        name="month_end_boundary",
        principal=Decimal("3000.00"),
        payment_start=date(2026, 8, 30),
        payments=(
            {"event_id": "month-end-1", "date": date(2026, 8, 31), "payment": "42.00"},
            {"event_id": "month-end-2", "date": date(2026, 9, 1), "payment": "21.00"},
        ),
    ),
    ParityCase(
        name="year_end_boundary",
        principal=Decimal("3000.00"),
        payment_start=date(2026, 12, 31),
        payments=(
            {"event_id": "year-end", "date": date(2026, 12, 31), "payment": "21.00"},
            {"event_id": "new-year", "date": date(2027, 1, 1), "payment": "21.00"},
        ),
    ),
    ParityCase(
        name="leap_day_boundary",
        principal=Decimal("3000.00"),
        payment_start=date(2028, 2, 28),
        payments=(
            {"event_id": "leap-1", "date": date(2028, 2, 28), "payment": "21.00"},
            {"event_id": "leap-2", "date": date(2028, 2, 29), "payment": "21.00"},
            {"event_id": "leap-3", "date": date(2028, 3, 1), "payment": "21.00"},
        ),
    ),
)


@pytest.mark.parametrize("case", PARITY_CASES, ids=lambda case: case.name)
def test_synthetic_desktop_server_parity_matrix(case: ParityCase) -> None:
    _assert_case_parity(case)


def test_latest_positive_payment_per_date_is_canonicalized_before_server_allocation() -> None:
    case = ParityCase(
        name="desktop_latest_positive_same_day_source_normalization",
        principal=Decimal("3000.00"),
        payment_start=date(2026, 8, 1),
        payments=(
            {"event_id": "superseded", "date": date(2026, 8, 1), "payment": "10.00"},
            {"event_id": "effective", "date": date(2026, 8, 1), "payment": "50.00"},
            {"event_id": "ignored-zero", "date": date(2026, 8, 2), "payment": "0.00"},
            {"event_id": "next", "date": date(2026, 8, 3), "payment": "42.00"},
        ),
    )

    _assert_case_parity(case)
    events = _effective_server_events(
        case.payments,
        payment_start=case.payment_start,
        as_of_date=date(2026, 8, 3),
    )
    assert [event.event_id for event in events] == ["effective", "next"]
    assert [event.amount for event in events] == [Decimal("50.00"), Decimal("42.00")]


def test_renewal_boundary_starts_a_new_independent_original_principal_cycle() -> None:
    old_cycle = ParityCase(
        name="renewal_old_cycle",
        principal=Decimal("5000.00"),
        payment_start=date(2026, 8, 1),
        payments=(
            {"event_id": "old-1", "date": date(2026, 8, 8), "payment": "100.00"},
            {"event_id": "old-2", "date": date(2026, 8, 9), "payment": "35.00"},
        ),
    )
    renewed_cycle = ParityCase(
        name="renewal_new_cycle",
        principal=Decimal("3000.00"),
        payment_start=date(2026, 8, 10),
        payments=(
            {"event_id": "renewed-1", "date": date(2026, 8, 10), "payment": "21.00"},
            {"event_id": "renewed-2", "date": date(2026, 8, 11), "payment": "121.00"},
        ),
    )

    _assert_case_parity(old_cycle)
    _assert_case_parity(renewed_cycle)

    renewed_server = allocate_seven_by_seven_payments(
        original_principal=renewed_cycle.principal,
        daily_interest_per_1000=DESKTOP_DAILY_INTEREST_PER_1000,
        payment_start=renewed_cycle.payment_start,
        events=_effective_server_events(
            renewed_cycle.payments,
            payment_start=renewed_cycle.payment_start,
            as_of_date=date(2026, 8, 11),
        ),
    )
    assert renewed_server.fixed_daily_interest == Decimal("21.00")
    assert renewed_server.allocations[0].gap_days == 1
    assert renewed_server.allocations[0].opening_interest_arrears == Decimal("0.00")
    assert renewed_server.allocations[0].opening_remaining_principal == Decimal("3000.00")


def test_advance_covered_date_metadata_is_financially_neutral_to_7x7_allocator() -> None:
    payment_start = date(2026, 8, 1)
    ordinary = ParityCase(
        name="ordinary_cash",
        principal=Decimal("5000.00"),
        payment_start=payment_start,
        payments=(
            {"event_id": "ordinary", "date": date(2026, 8, 1), "payment": "210.00"},
        ),
    )
    advance = ParityCase(
        name="advance_cash_same_amount_and_date",
        principal=Decimal("5000.00"),
        payment_start=payment_start,
        payments=(
            {
                "event_id": "advance",
                "date": date(2026, 8, 1),
                "payment": "210.00",
                "entry_type": "advance",
                "covered_dates": (
                    date(2026, 8, 1),
                    date(2026, 8, 2),
                    date(2026, 8, 5),
                ),
            },
        ),
    )

    ordinary_desktop = allocate_x7_payments(
        ordinary.principal,
        ordinary.payment_start,
        ordinary.payments,
        date(2026, 8, 1),
    )
    advance_desktop = allocate_x7_payments(
        advance.principal,
        advance.payment_start,
        advance.payments,
        date(2026, 8, 1),
    )
    assert ordinary_desktop == advance_desktop

    ordinary_server = allocate_seven_by_seven_payments(
        original_principal=ordinary.principal,
        daily_interest_per_1000=DESKTOP_DAILY_INTEREST_PER_1000,
        payment_start=ordinary.payment_start,
        events=_effective_server_events(
            ordinary.payments,
            payment_start=ordinary.payment_start,
            as_of_date=date(2026, 8, 1),
        ),
    )
    advance_server = allocate_seven_by_seven_payments(
        original_principal=advance.principal,
        daily_interest_per_1000=DESKTOP_DAILY_INTEREST_PER_1000,
        payment_start=advance.payment_start,
        events=_effective_server_events(
            advance.payments,
            payment_start=advance.payment_start,
            as_of_date=date(2026, 8, 1),
        ),
    )
    assert ordinary_server.total_interest_paid == advance_server.total_interest_paid
    assert ordinary_server.total_principal_paid == advance_server.total_principal_paid
    assert ordinary_server.closing_remaining_principal == advance_server.closing_remaining_principal
    assert ordinary_server.closing_interest_arrears == advance_server.closing_interest_arrears
