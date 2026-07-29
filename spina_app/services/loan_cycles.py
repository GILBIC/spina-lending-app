"""Loan-cycle timing and completion summaries shared across SPINA.

Wave 75 extracts reusable cycle logic from the large desktop dashboard function.
This module does not query a database and does not import Tkinter.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Callable, Mapping

from spina_app.calculation_rules import (
    allocate_x7_payments,
    normalize_loan_type,
    shift_due_date_for_renewal,
)
from spina_app.utilities.dashboard import _spina_dash__status_for

StatusResolver = Callable[[float, float, int | None], tuple[str, int]]


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


def normalize_payment_start_offset(value: Any) -> int:
    """Normalize legacy offsets to the supported zero-day or one-day behavior."""
    try:
        parsed = int(value or 0)
    except Exception:
        parsed = 1
    return 1 if parsed >= 1 else 0


def build_cycle_timing(
    base_release: Any,
    original_due: Any,
    latest_renewal: Any = None,
    pay_start_offset_days: Any = 1,
    today: Any = None,
) -> dict[str, Any]:
    """Build the active cycle's release, payment-start, and due-date timing.

    A later renewal becomes the active release date. The original loan-cycle length
    is preserved when calculating the renewed due date.
    """
    today_d = _as_date(today) or date.today()
    base = _as_date(base_release)
    renewal = _as_date(latest_renewal)

    latest = base
    if renewal and (latest is None or renewal > latest):
        latest = renewal
    if latest is None:
        latest = today_d

    offset = normalize_payment_start_offset(pay_start_offset_days)
    payment_start = latest + timedelta(days=offset)
    due_date = shift_due_date_for_renewal(base, original_due, latest)

    days_left: int | None = None
    time_passed_pct = 0.0
    if due_date:
        days_left = (due_date - today_d).days
        try:
            cycle_days = max(1, (due_date - payment_start).days)
            elapsed = max(0, (today_d - payment_start).days)
            time_passed_pct = min(999.0, (elapsed / cycle_days) * 100.0)
        except Exception:
            time_passed_pct = 0.0

    return {
        "date_released": base,
        "latest_released": latest,
        "payment_start": payment_start,
        "due_date": due_date,
        "days_left": days_left,
        "time_passed_pct": float(time_passed_pct),
        "pay_start_offset_days": offset,
    }


def finalize_cycle_record(
    record: Mapping[str, Any],
    as_of_date: Any = None,
    status_resolver: StatusResolver | None = None,
) -> dict[str, Any]:
    """Return a completed dashboard/service record without mutating the input.

    Regular loans use the accumulated ``paid`` value already collected by the
    database adapter. 7x7 loans allocate effective daily payments to fixed daily
    interest first and principal second.
    """
    rec = dict(record or {})
    today_d = _as_date(as_of_date) or date.today()
    loan_type = normalize_loan_type(rec.get("loan_type"))
    total = max(0.0, _as_float(rec.get("total_to_pay")))

    if loan_type == "7x7":
        allocation = allocate_x7_payments(
            rec.get("principal"),
            rec.get("payment_start"),
            rec.get("_x7_payments") or (),
            today_d,
        )
        paid = _as_float(allocation.get("principal_paid"))
        remaining = _as_float(allocation.get("remaining_principal"))
        completion = _as_float(allocation.get("completion_pct"))
        rec["total_collected"] = _as_float(allocation.get("total_collected"))
        rec["interest_paid"] = _as_float(allocation.get("interest_paid"))
        rec["interest_arrears"] = _as_float(allocation.get("interest_arrears"))
        rec["payoff_with_interest"] = _as_float(allocation.get("payoff_with_interest"))
        rec["daily_interest"] = _as_float(allocation.get("daily_interest"))
        rec["interest_basis_principal"] = _as_float(
            allocation.get("interest_basis_principal")
        )
    else:
        paid = _as_float(rec.get("paid"))
        remaining = max(0.0, total - paid)
        completion = (paid / total * 100.0) if total > 0.0 else 0.0

    resolver = status_resolver or _spina_dash__status_for
    status, priority = resolver(completion, remaining, rec.get("days_left"))
    rec["paid"] = float(paid)
    rec["remaining"] = float(remaining)
    rec["completion_pct"] = float(completion)
    rec["status"] = status
    rec["priority"] = int(priority)
    rec.pop("_x7_payments", None)
    return rec


def cycle_sort_key(record: Mapping[str, Any]) -> tuple[Any, ...]:
    """Stable dashboard ordering used after cycle records are finalized."""
    return (
        int(_as_float(record.get("priority"), 99)),
        -_as_float(record.get("principal")),
        -_as_float(record.get("completion_pct")),
        str(record.get("name") or ""),
    )
