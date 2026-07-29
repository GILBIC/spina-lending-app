"""Pure Cash Control forecasting and reserve rules for SPINA."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Callable

from spina_app.calculation_rules import allocate_x7_payments, normalize_loan_type
from spina_app.repositories.cash_control import fetch_x7_cycle_payments
from spina_app.repositories.dashboard import fetch_dashboard_rows
from spina_app.utilities.dates import _spina_cashctl__valid_date
from spina_app.utilities.numbers import (
    _spina_cashctl__int_range,
    _spina_cashctl__parse_amount,
)

DashboardFetcher = Callable[[Any], list[dict[str, Any]]]
PaymentFetcher = Callable[..., list[tuple[Any, float]]]
PayoffEstimator = Callable[..., float]


def parse_percent(value: Any, default: float = 10.0) -> float:
    """Parse ``10``, ``10%``, or decimal-style ``0.10`` into 0..100."""
    try:
        text = str(value or "").replace("%", "").strip()
        if not text:
            return float(default)
        percent = float(text)
        if 0 < percent <= 1:
            percent *= 100.0
        return max(0.0, min(100.0, percent))
    except Exception:
        return float(default)


def _as_date(value: Any, fallback: date | None = None) -> date:
    if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
        return value
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except Exception:
        return fallback or date.today()


def estimated_payoff_with_interest(
    app: Any,
    record: dict[str, Any],
    as_of_date: Any = None,
    *,
    payment_fetcher: PaymentFetcher = fetch_x7_cycle_payments,
) -> float:
    """Estimate renewal payoff while preserving fixed-principal 7x7 interest."""
    if normalize_loan_type(record.get("loan_type")) != "7x7":
        try:
            return round(max(0.0, float(record.get("remaining") or 0.0)), 2)
        except Exception:
            return 0.0

    try:
        principal = float(record.get("principal") or 0.0)
    except Exception:
        principal = 0.0
    if principal <= 0:
        return 0.0

    start_date = _as_date(record.get("payment_start"), date.today())
    end_date = _as_date(as_of_date, date.today())
    if end_date < start_date:
        end_date = start_date

    try:
        payments = payment_fetcher(app, record, start_date, end_date)
    except Exception:
        payments = []
    allocation = allocate_x7_payments(principal, start_date, payments, end_date)
    return round(float(allocation.get("payoff_with_interest") or 0.0), 2)


def _selected_date_from_app(app: Any) -> str:
    try:
        variable = getattr(app, "cashctl_date_var", None)
        if variable is not None and hasattr(variable, "get"):
            return _spina_cashctl__valid_date(variable.get())
    except Exception:
        pass
    return date.today().strftime("%Y-%m-%d")


def build_reserve_rows(
    app: Any,
    forecast_days: Any = 14,
    *,
    dashboard_fetcher: DashboardFetcher = fetch_dashboard_rows,
    payoff_estimator: PayoffEstimator = estimated_payoff_with_interest,
    selected_date: Any = None,
) -> list[dict[str, Any]]:
    """Reserve the current principal for every active client, urgent clients first."""
    days = _spina_cashctl__int_range(forecast_days, 14, 1, 120)

    try:
        rows = list(getattr(app, "_dashboard_rows", []) or [])
        if not rows and hasattr(app, "_dashboard_fetch_rows"):
            rows = list(app._dashboard_fetch_rows() or [])
    except Exception:
        rows = []
    if not rows:
        try:
            rows = list(dashboard_fetcher(app) or [])
        except Exception:
            rows = []

    base_date = _as_date(
        _spina_cashctl__valid_date(selected_date or _selected_date_from_app(app)),
        date.today(),
    )
    payoff_date = base_date + timedelta(days=days)

    reserve_rows: list[dict[str, Any]] = []
    for row in rows:
        try:
            status = str(row.get("status") or "")
            completion = float(row.get("completion_pct") or 0.0)
            raw_days_left = row.get("days_left")
            try:
                days_left = (
                    int(raw_days_left)
                    if raw_days_left is not None and str(raw_days_left) != ""
                    else None
                )
            except Exception:
                days_left = None

            if status == "Complete" or completion >= 99.999:
                reason, priority = "Complete / ask renewal", 5
            elif completion >= 90:
                reason, priority = "90%+ paid", 10
            elif completion >= 75:
                reason, priority = "75%+ paid", 20
            elif days_left is not None and days_left < 0:
                reason, priority = "Overdue", 30
            elif days_left is not None and days_left <= days:
                reason, priority = "Due within %s day(s)" % days, 40
            else:
                reason, priority = "All active client", 90

            reserve = dict(row)
            try:
                reserve["reserve_amount"] = round(
                    float(reserve.get("principal") or 0.0), 2
                )
            except Exception:
                reserve["reserve_amount"] = 0.0
            try:
                reserve["expected_payoff_collection"] = round(
                    payoff_estimator(app, reserve, payoff_date), 2
                )
            except Exception:
                reserve["expected_payoff_collection"] = round(
                    max(0.0, float(reserve.get("remaining") or 0.0)), 2
                )
            if normalize_loan_type(reserve.get("loan_type")) == "7x7":
                reason += " / interest included"
            reserve["reserve_reason"] = reason
            reserve["_cashctl_sort_priority"] = priority
            reserve_rows.append(reserve)
        except Exception:
            continue

    reserve_rows.sort(
        key=lambda item: (
            int(item.get("_cashctl_sort_priority") or item.get("priority") or 80),
            -float(item.get("reserve_amount") or 0.0),
            int(item.get("days_left") or 9999),
            str(item.get("name") or ""),
        )
    )
    return reserve_rows


def calculate_safe_cash(
    *,
    cash_on_hand: Any,
    today_collection: Any,
    average_daily_collection: Any,
    forecast_days: Any,
    reserve_rows: list[dict[str, Any]],
    buffer_percent: Any = 10.0,
) -> dict[str, float]:
    """Calculate current and forecast-safe release amounts without UI side effects."""
    days = _spina_cashctl__int_range(forecast_days, 14, 1, 120)
    buffer_pct = parse_percent(buffer_percent, default=10.0)
    cash = _spina_cashctl__parse_amount(cash_on_hand)
    collected = _spina_cashctl__parse_amount(today_collection)
    average = _spina_cashctl__parse_amount(average_daily_collection)

    reserve_total = round(
        sum(float(row.get("reserve_amount") or 0.0) for row in reserve_rows), 2
    )
    expected_payoff = round(
        sum(
            max(
                0.0,
                float(
                    row.get(
                        "expected_payoff_collection", row.get("remaining", 0.0)
                    )
                    or 0.0
                ),
            )
            for row in reserve_rows
        ),
        2,
    )
    net_renewal_need = round(max(0.0, reserve_total - expected_payoff), 2)
    future_cash = round(average * days, 2)

    current_available = round(cash + collected, 2)
    current_buffer = round(max(0.0, current_available) * (buffer_pct / 100.0), 2)
    safe_now = round(current_available - net_renewal_need - current_buffer, 2)

    forecast_available = round(current_available + future_cash, 2)
    forecast_buffer = round(max(0.0, forecast_available) * (buffer_pct / 100.0), 2)
    forecast_safe = round(
        forecast_available - net_renewal_need - forecast_buffer, 2
    )

    return {
        "forecast_days": float(days),
        "buffer_percent": round(buffer_pct, 4),
        "reserve_total": reserve_total,
        "expected_renewal_payoff": expected_payoff,
        "net_renewal_need": net_renewal_need,
        "future_cash": future_cash,
        "current_available": current_available,
        "current_buffer": current_buffer,
        "safe_now": safe_now,
        "forecast_available": forecast_available,
        "forecast_buffer": forecast_buffer,
        "forecast_safe": forecast_safe,
    }
