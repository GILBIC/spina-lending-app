"""Pure lending calculations shared by dashboards, reports, and regression tests.

Wave 74 centralizes the rules that previously lived inside large presentation
functions. The functions in this module do not access Tkinter or a database.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Iterable, Mapping


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


def normalize_loan_type(value: Any) -> str:
    try:
        text = str(value or "").strip().lower().replace("×", "x").replace(" ", "")
    except Exception:
        text = ""
    return "7x7" if text in {"7x7", "7x7emer", "emer", "emergency"} or "7x7" in text else "Regular"


def normalized_total_to_pay(
    loan_type: Any,
    principal: Any,
    interest_amount: Any = 0.0,
    total_to_pay: Any = 0.0,
) -> float:
    """Return the protected cycle target used for balance calculations.

    Regular loans use principal plus fixed interest when an older record stores
    only principal in ``total_to_pay``. 7x7 completion is principal-based because
    its daily interest is allocated separately.
    """
    lt = normalize_loan_type(loan_type)
    principal_f = max(0.0, _as_float(principal))
    interest_f = max(0.0, _as_float(interest_amount))
    total_f = max(0.0, _as_float(total_to_pay))

    if lt == "7x7":
        return round(principal_f, 2)
    if total_f <= 0.0 or (interest_f > 0.0 and abs(total_f - principal_f) < 0.01):
        total_f = principal_f + interest_f
    return round(max(0.0, total_f), 2)


def shift_due_date_for_renewal(
    base_release: Any,
    original_due: Any,
    latest_release: Any,
) -> date | None:
    """Preserve the original cycle length when a loan is renewed.

    A renewal always starts a new cycle when ``latest_release`` is later than the
    original release. This avoids retaining a due date that is still in the
    future but belongs to the old cycle.
    """
    base = _as_date(base_release)
    due = _as_date(original_due)
    latest = _as_date(latest_release)
    if not latest:
        return due
    if not base or not due or latest <= base:
        return due
    cycle_days = (due - base).days
    if cycle_days <= 0:
        return due
    return latest + timedelta(days=cycle_days)


def ceil_thousand_units(amount: Any) -> int:
    value = max(0.0, _as_float(amount))
    if value <= 0.0:
        return 0
    return max(1, int((value + 999.999999) // 1000))


def x7_daily_interest(loan_principal: Any) -> float:
    """Return fixed 7x7 daily interest from the loan's recorded principal.

    Every started ₱1,000 of the current loan principal carries ₱7 per day.
    The result remains fixed throughout that loan cycle even as payments reduce
    the remaining principal. It changes only when the recorded principal is
    deliberately updated or a new/renewed loan cycle uses a different principal.
    """
    return float(ceil_thousand_units(loan_principal)) * 7.0


def _payment_parts(item: Any) -> tuple[Any, Any]:
    if isinstance(item, Mapping):
        return item.get("date", item.get("d")), item.get("payment", item.get("amount", item.get("amt")))
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
    """Allocate effective daily 7x7 payments to interest first, then principal.

    The latest positive payment for a date wins, matching Data Bank's one-effective-
    payment-per-day rule. Daily interest is fixed from the recorded loan principal
    for the whole cycle; a falling remaining balance does not lower it.
    """
    principal_f = max(0.0, _as_float(principal))
    fixed_daily_interest = x7_daily_interest(principal_f)
    start = _as_date(payment_start) or date.today()
    end = _as_date(as_of_date) or date.today()
    if end < start:
        end = start

    effective_by_day: dict[date, float] = {}
    for item in payments or ():
        raw_date, raw_amount = _payment_parts(item)
        pay_date = _as_date(raw_date)
        amount = _as_float(raw_amount)
        if pay_date is None or amount <= 0.0 or pay_date < start or pay_date > end:
            continue
        effective_by_day[pay_date] = amount

    remaining_principal = principal_f
    interest_arrears = 0.0
    interest_paid_total = 0.0
    principal_paid_total = 0.0
    total_collected = 0.0
    previous_date = start - timedelta(days=1)

    for pay_date in sorted(effective_by_day):
        amount = effective_by_day[pay_date]
        gap = max(1, (pay_date - previous_date).days)
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
    completion = (principal_paid_total / principal_f * 100.0) if principal_f > 0.0 else 0.0
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
