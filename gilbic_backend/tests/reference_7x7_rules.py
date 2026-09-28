"""Frozen pre-retirement 7x7 calculation oracle for server regression tests only.

Extracted from f2b15fb1 calculation_rules.py; no UI, accounts or database access.
The authoritative runtime remains gilbic_backend. Do not import from production.
"""
# Preserve the historical fallback/date/clamp behavior of this independent oracle.
# These are test-only comparisons, never production authentication or calculations.
# ruff: noqa: BLE001, DTZ007, DTZ011, PLR1730

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, datetime, timedelta
from typing import Any


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value or 0.0)
    except Exception:
        return float(default)


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        text = str(value or "").strip()[:10]
        return datetime.strptime(text, "%Y-%m-%d").date() if text else None
    except Exception:
        return None


def ceil_thousand_units(amount: Any) -> int:
    value = max(0.0, _as_float(amount))
    if value <= 0.0:
        return 0
    return max(1, int((value + 999.999999) // 1000))


def x7_daily_interest(loan_principal: Any) -> float:
    """Return fixed 7x7 daily interest from the loan's recorded principal.

    Every started â‚±1,000 of the current loan principal carries â‚±7 per day.
    The result remains fixed throughout that loan cycle even as payments reduce
    the remaining principal. It changes only when the recorded principal is
    deliberately updated or a new/renewed loan cycle uses a different principal.
    """
    return float(ceil_thousand_units(loan_principal)) * 7.0


def _payment_parts(item: Any) -> tuple[Any, Any]:
    if isinstance(item, Mapping):
        return item.get("date", item.get("d")), item.get(
            "payment", item.get("amount", item.get("amt"))
        )
    try:
        return item[0], item[1]
    except Exception:
        return None, None


def allocate_x7_payments(
    principal: Any,
    payment_start: Any,
    payments: Iterable[Any],
    as_of_date: Any = None,
) -> dict[str, float]:
    """Allocate every distinct positive 7x7 receipt to interest first, then principal.

    Daily interest is fixed from the recorded loan principal for the whole cycle;
    a falling remaining balance does not lower it. Multiple genuine receipts may
    occur on the same calendar date. They are preserved in authoritative input
    order: the first receipt for a date accrues the elapsed calendar-day interest,
    while later same-day receipts accrue zero additional days and continue settling
    that day's interest/principal. Technical retries must be removed by the
    transaction/idempotency layer before reaching this pure allocator.
    """
    principal_f = max(0.0, _as_float(principal))
    fixed_daily_interest = x7_daily_interest(principal_f)
    start = _as_date(payment_start) or date.today()
    end = _as_date(as_of_date) or date.today()
    if end < start:
        end = start

    effective_receipts: list[tuple[date, int, float]] = []
    for index, item in enumerate(payments or ()):
        raw_date, raw_amount = _payment_parts(item)
        pay_date = _as_date(raw_date)
        amount = _as_float(raw_amount)
        if pay_date is None or amount <= 0.0 or pay_date < start or pay_date > end:
            continue
        effective_receipts.append((pay_date, index, amount))
    effective_receipts.sort(key=lambda row: (row[0], row[1]))

    remaining_principal = principal_f
    interest_arrears = 0.0
    interest_paid_total = 0.0
    principal_paid_total = 0.0
    total_collected = 0.0
    previous_date = start - timedelta(days=1)

    for pay_date, _, amount in effective_receipts:
        gap = max(0, (pay_date - previous_date).days)
        interest_due = fixed_daily_interest * float(gap) + interest_arrears
        interest_paid = min(amount, interest_due)
        principal_paid = min(remaining_principal, max(0.0, amount - interest_paid))

        interest_paid_total += interest_paid
        principal_paid_total += principal_paid
        total_collected += amount
        remaining_principal = max(0.0, remaining_principal - principal_paid)
        interest_arrears = max(0.0, interest_due - interest_paid)
        previous_date = pay_date

        if remaining_principal <= 0.004 and interest_arrears <= 0.004:
            remaining_principal = 0.0
            interest_arrears = 0.0
            break

    if remaining_principal > 0.0:
        tail_gap = max(0, (end - previous_date).days)
        if tail_gap:
            interest_arrears += fixed_daily_interest * float(tail_gap)

    payoff = max(0.0, remaining_principal + interest_arrears)
    completion = (
        (principal_paid_total / principal_f * 100.0) if principal_f > 0.0 else 0.0
    )
    return {
        "principal": round(principal_f, 2),
        "interest_basis_principal": round(principal_f, 2),
        "daily_interest": round(fixed_daily_interest, 2),
        "total_collected": round(total_collected, 2),
        "interest_paid": round(interest_paid_total, 2),
        "principal_paid": round(principal_paid_total, 2),
        "remaining_principal": round(remaining_principal, 2),
        "interest_arrears": round(interest_arrears, 2),
        "payoff_with_interest": round(payoff, 2),
        "completion_pct": float(completion),
    }
