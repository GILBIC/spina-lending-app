"""Complete Cash Control controller and runtime installer for SPINA Wave 77."""
from __future__ import annotations

from typing import Any, Callable

from spina_app.repositories.cash_control import (
    fetch_average_collection,
    fetch_collection_totals,
)
from spina_app.services.cash_control import build_reserve_rows, calculate_safe_cash
from spina_app.tabs.cash_control import (
    configure_cash_control_dependencies,
    _spina_v21_cash_build_tab,
    _spina_v21_cash_draw_charts,
)
from spina_app.ui_helpers import (
    _spina_v20_round_rect,
    _spina_v21_cash_set_card,
)
from spina_app.utilities.dates import _spina_cashctl__valid_date, _spina_dash__date_text
from spina_app.utilities.formatting import (
    _spina_cashctl__fmt_pct,
    _spina_dash__fmt_money,
    _spina_v18_fmt_money_compact,
)
from spina_app.utilities.numbers import _spina_cashctl__int_range

LogCallback = Callable[[str, BaseException | None], Any]
SuppressedLogCallback = Callable[[str, str, BaseException | None], Any]


def _safe_log(
    callback: LogCallback | None,
    context: str,
    exc: BaseException | None = None,
) -> None:
    if not callable(callback):
        return
    try:
        callback(context, exc)
    except Exception:
        pass


def _safe_suppressed_log(
    callback: SuppressedLogCallback | None,
    key: str,
    message: str,
    exc: BaseException | None = None,
) -> None:
    if not callable(callback):
        return
    try:
        callback(key, message, exc)
    except Exception:
        pass


def _fmt_money(value: Any) -> str:
    try:
        return _spina_dash__fmt_money(value)
    except Exception:
        try:
            return "PHP {:,.2f}".format(float(value or 0.0))
        except Exception:
            return "PHP 0.00"


def _get_var(app: Any, name: str, default: str) -> str:
    try:
        variable = getattr(app, name, None)
        if variable is not None and hasattr(variable, "get"):
            return str(variable.get() or default)
    except Exception:
        pass
    return default


def _set_var(app: Any, name: str, value: str) -> None:
    try:
        variable = getattr(app, name, None)
        if variable is not None and hasattr(variable, "set"):
            variable.set(value)
    except Exception:
        pass


def refresh_cash_control(
    app: Any,
    *,
    log_exc: LogCallback | None = None,
) -> None:
    """Refresh the modern Cash Control cards, charts, decision, and reserve table."""
    try:
        if not hasattr(app, "tab_cash_control"):
            return

        selected_date = _spina_cashctl__valid_date(
            _get_var(app, "cashctl_date_var", "")
        )
        if _get_var(app, "cashctl_date_var", "")[:10] != selected_date:
            _set_var(app, "cashctl_date_var", selected_date)
            return

        days = _spina_cashctl__int_range(
            _get_var(app, "cashctl_forecast_days_var", "14"), 14, 1, 120
        )
        average_window = _spina_cashctl__int_range(
            _get_var(app, "cashctl_avg_window_days_var", "30"), 30, 1, 365
        )
        totals = fetch_collection_totals(app, selected_date, log_exc=log_exc)
        average = fetch_average_collection(
            app, selected_date, average_window, log_exc=log_exc
        )
        reserve_rows = build_reserve_rows(
            app, days, selected_date=selected_date
        )
        summary = calculate_safe_cash(
            cash_on_hand=_get_var(app, "cashctl_cash_on_hand_var", "0"),
            today_collection=totals.get("combined", 0.0),
            average_daily_collection=average.get("average", 0.0),
            forecast_days=days,
            reserve_rows=reserve_rows,
            buffer_percent=_get_var(app, "cashctl_buffer_percent_var", "10"),
        )

        combined = float(totals.get("combined") or 0.0)
        regular = float(totals.get("regular") or 0.0)
        x7 = float(totals.get("7x7") or 0.0)
        other = float(totals.get("other") or 0.0)
        average_daily = float(average.get("average") or 0.0)
        active_days = int(average.get("active_days") or 0)

        _set_var(
            app,
            "cashctl_collection_var",
            "Today Collection: %s" % _fmt_money(combined),
        )
        breakdown = "Regular: %s • 7x7: %s" % (
            _fmt_money(regular),
            _fmt_money(x7),
        )
        if abs(other) >= 0.005:
            breakdown += " • Other: %s" % _fmt_money(other)
        _set_var(app, "cashctl_breakdown_var", breakdown)
        _set_var(
            app,
            "cashctl_avg_collection_var",
            "Average Daily Collection: %s" % _fmt_money(average_daily),
        )
        _set_var(
            app,
            "cashctl_future_cash_var",
            "Forecast Collection: %s" % _fmt_money(summary["future_cash"]),
        )
        _set_var(
            app,
            "cashctl_current_available_var",
            "Current Available: %s" % _fmt_money(summary["current_available"]),
        )
        _set_var(
            app,
            "cashctl_forecast_available_var",
            "Forecast Available: %s"
            % _fmt_money(summary["forecast_available"]),
        )
        _set_var(
            app,
            "cashctl_reserve_var",
            "Renewal Release Reserve: %s" % _fmt_money(summary["reserve_total"]),
        )
        _set_var(
            app,
            "cashctl_renewal_payoff_var",
            "Expected Renewal Payoff: %s"
            % _fmt_money(summary["expected_renewal_payoff"]),
        )
        _set_var(
            app,
            "cashctl_net_renewal_var",
            "Net Renewal Cash Need: %s"
            % _fmt_money(summary["net_renewal_need"]),
        )
        _set_var(
            app,
            "cashctl_buffer_amount_var",
            "Emergency Buffer: %s" % _fmt_money(summary["current_buffer"]),
        )
        _set_var(
            app,
            "cashctl_safe_now_var",
            "Safe Now: %s" % _fmt_money(max(0.0, summary["safe_now"])),
        )
        _set_var(
            app,
            "cashctl_forecast_safe_var",
            "Forecast Safe: %s"
            % _fmt_money(max(0.0, summary["forecast_safe"])),
        )

        safe_now = float(summary["safe_now"])
        forecast_safe = float(summary["forecast_safe"])
        if safe_now > 0 and forecast_safe > safe_now:
            decision = (
                "Safe now is %s. Forecast safe is %s if the average collection "
                "arrives."
                % (_fmt_money(safe_now), _fmt_money(forecast_safe))
            )
        elif safe_now > 0:
            decision = (
                "Safe now is %s based on cash on hand and today's collection only."
                % _fmt_money(safe_now)
            )
        elif abs(safe_now) < 0.005:
            decision = (
                "No safe amount is available now after renewal need and emergency "
                "buffer."
            )
        else:
            decision = (
                "Do not release new loans now. Current cash is short by %s after "
                "renewal need and emergency buffer."
                % _fmt_money(abs(safe_now))
            )
        if active_days <= 0:
            decision += (
                " Forecast is PHP 0.00 because no collection history was found in "
                "the selected window."
            )
        _set_var(app, "cashctl_decision_var", decision)
        _set_var(
            app,
            "cashctl_table_summary_var",
            "%s active client(s) • Reserve %s • Expected payoff %s"
            % (
                len(reserve_rows),
                _fmt_money(summary["reserve_total"]),
                _fmt_money(summary["expected_renewal_payoff"]),
            ),
        )

        _spina_v21_cash_set_card(
            app,
            "safe_now",
            _fmt_money(max(0.0, safe_now)),
            "Real cash only",
        )
        _spina_v21_cash_set_card(
            app,
            "forecast_safe",
            _fmt_money(max(0.0, forecast_safe)),
            "%s-day forecast" % days,
        )
        _spina_v21_cash_set_card(
            app, "collection", _fmt_money(combined), selected_date
        )
        _spina_v21_cash_set_card(
            app,
            "net_need",
            _fmt_money(summary["net_renewal_need"]),
            "Reserve minus expected payoff",
        )
        _spina_v21_cash_set_card(
            app,
            "reserve",
            _fmt_money(summary["reserve_total"]),
            "%s active client(s)" % len(reserve_rows),
        )
        _spina_v21_cash_set_card(
            app,
            "buffer",
            _fmt_money(summary["current_buffer"]),
            _spina_cashctl__fmt_pct(summary["buffer_percent"]),
        )
        _spina_v21_cash_set_card(
            app,
            "average",
            _fmt_money(average_daily),
            "%s active day(s)" % active_days,
        )
        _spina_v21_cash_set_card(
            app,
            "available",
            _fmt_money(summary["current_available"]),
            "Cash on hand + today",
        )

        tree = getattr(app, "cashctl_tree", None)
        if tree is not None:
            for item_id in tree.get_children():
                tree.delete(item_id)
            for row in reserve_rows:
                completion = float(row.get("completion_pct") or 0.0)
                days_left = row.get("days_left")
                if completion >= 99.999:
                    tag = "finish"
                elif completion >= 75:
                    tag = "near"
                elif days_left is not None and int(days_left) < 0:
                    tag = "overdue"
                elif days_left is not None and int(days_left) <= days:
                    tag = "due"
                else:
                    tag = ""
                tree.insert(
                    "",
                    "end",
                    values=(
                        row.get("status") or "",
                        row.get("name") or "",
                        row.get("loan_type") or "",
                        row.get("area") or "",
                        _fmt_money(row.get("principal") or 0.0),
                        _spina_cashctl__fmt_pct(completion),
                        _fmt_money(row.get("remaining") or 0.0),
                        _spina_dash__date_text(row.get("due_date")),
                        "" if days_left is None else str(days_left),
                        _fmt_money(row.get("reserve_amount") or 0.0),
                        row.get("reserve_reason") or "",
                    ),
                    tags=(tag,) if tag else (),
                )

        app._cashctl_last_data = {
            "date": selected_date,
            "regular": regular,
            "7x7": x7,
            "other": other,
            "combined": combined,
            "current_available": summary["current_available"],
            "net_need": summary["net_renewal_need"],
            "buffer_now": summary["current_buffer"],
            "safe_now": safe_now,
            "forecast_safe": forecast_safe,
            "reserve_rows": reserve_rows,
        }
        _spina_v21_cash_draw_charts(app, app._cashctl_last_data)
        try:
            if hasattr(app, "status_var"):
                app.status_var.set(
                    "Cash Control refreshed. All active clients are included in the "
                    "renewal reserve."
                )
        except Exception:
            pass
    except Exception as exc:
        _safe_log(log_exc, "cash_control.refresh", exc)


def apply_cash_control_role(app: Any) -> None:
    try:
        if not hasattr(app, "nb") or not hasattr(app, "tab_cash_control"):
            return
        role = (getattr(app, "user_role", "") or "Admin").strip()
        if role == "System":
            try:
                app.nb.hide(app.tab_cash_control)
            except Exception:
                pass
            return
        try:
            tabs = list(app.nb.tabs())
        except Exception:
            tabs = []
        if str(app.tab_cash_control) not in tabs:
            try:
                app.nb.insert(2, app.tab_cash_control, text="Cash Control")
            except Exception:
                try:
                    app.nb.add(app.tab_cash_control, text="Cash Control")
                except Exception:
                    pass
    except Exception:
        pass


def install_cash_control_feature(
    app_class: type | None,
    *,
    log_exc: LogCallback | None = None,
    log_suppressed_once: SuppressedLogCallback | None = None,
) -> bool:
    """Install Cash Control once while preserving role and mode hooks."""
    if app_class is None:
        return False
    if bool(getattr(app_class, "_spina_cash_control_wave77_installed", False)):
        return True

    def cash_log(context: str, exc: BaseException | None = None) -> None:
        _safe_log(log_exc, context, exc)

    try:
        missing = configure_cash_control_dependencies(
            {
                "_log_exc": cash_log,
                "_spina_v21_cash_money_short": _spina_v18_fmt_money_compact,
                "_spina_v21_cash_round_rect": _spina_v20_round_rect,
            }
        )
        if missing:
            raise RuntimeError(
                "Cash Control module dependencies unavailable: "
                + ", ".join(missing)
            )

        app_class._build_cash_control_tab = _spina_v21_cash_build_tab
        app_class.refresh_cash_control = lambda self: refresh_cash_control(
            self, log_exc=cash_log
        )
        app_class._cash_control_get_collection_totals = (
            lambda self, selected_date: fetch_collection_totals(
                self, selected_date, log_exc=cash_log
            )
        )
        app_class._cash_control_get_average_collection = (
            lambda self, selected_date, window_days=30: fetch_average_collection(
                self, selected_date, window_days, log_exc=cash_log
            )
        )
        app_class._cash_control_reserve_rows = (
            lambda self, forecast_days=14: build_reserve_rows(self, forecast_days)
        )

        original_init = app_class.__init__

        def init_with_cash_control(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            try:
                self._build_cash_control_tab()
                apply_cash_control_role(self)
            except Exception as exc:
                cash_log("cash_control.init_hook", exc)

        app_class.__init__ = init_with_cash_control

        original_apply_role = getattr(app_class, "apply_role_access", None)
        if callable(original_apply_role):
            def apply_role_with_cash_control(self, *args, **kwargs):
                result = original_apply_role(self, *args, **kwargs)
                apply_cash_control_role(self)
                return result

            app_class.apply_role_access = apply_role_with_cash_control

        original_mode_change = getattr(app_class, "_on_mode_change", None)
        if callable(original_mode_change):
            def mode_change_with_cash_control(self, *args, **kwargs):
                result = original_mode_change(self, *args, **kwargs)
                try:
                    self.refresh_cash_control()
                except Exception:
                    pass
                return result

            app_class._on_mode_change = mode_change_with_cash_control

        app_class._spina_cash_control_wave77_installed = True
        return True
    except Exception as exc:
        _safe_suppressed_log(
            log_suppressed_once,
            "cash_control_wave77_install_failed",
            "Wave 77 Cash Control feature installation failed",
            exc,
        )
        cash_log("cash_control.wave77.install", exc)
        return False
