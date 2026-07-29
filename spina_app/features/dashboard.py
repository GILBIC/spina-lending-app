"""Complete runtime installer for the modular SPINA dashboard.

The desktop entry module calls :func:`install_dashboard_feature` once. Presentation,
charts, database reads, business rules, role handling, and runtime hooks then remain
inside ``spina_app`` modules instead of the monolithic entry file.
"""
from __future__ import annotations

import sys
from typing import Any, Callable

from spina_app.calculation_rules import normalize_loan_type
from spina_app.dashboard_chart_presentation import (
    configure_dashboard_chart_dependencies,
    _spina_v18_draw_dashboard_charts,
    _spina_v20_draw_dashboard_charts,
)
from spina_app.repositories.dashboard import fetch_dashboard_rows
from spina_app.tabs.dashboard import (
    configure_legacy_dashboard_feature,
    _spina_apply_dashboard_role,
    _spina_configure_dashboard_tree_theme,
    _spina_v17_build_dashboard_tab,
    _spina_v18_patch_dashboard_chart_cards,
    _spina_v19_visible_dashboard_rows,
    _spina_v20_populate_dashboard_tree,
    _spina_v20_refresh_dashboard,
)
from spina_app.theme_palettes import (
    _spina_v18_dashboard_palette,
    _spina_v20_dash_palette,
)
from spina_app.ui_helpers import (
    _spina_v18_draw_round_rect,
    _spina_v20_round_rect,
)
from spina_app.utilities.formatting import _spina_v18_fmt_money_compact

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


def _mode_text(app: Any) -> str:
    try:
        mode_var = getattr(app, "mode_var", None)
        if mode_var is not None and hasattr(mode_var, "get"):
            return str(mode_var.get() or "Regular")
    except Exception:
        pass
    return "Regular"


def _install_compatibility_globals(app_class: type) -> None:
    """Restore globals still consumed by non-Dashboard legacy fallback paths."""
    try:
        module_name = str(getattr(app_class, "__module__", "") or "")
        app_module = sys.modules.get(module_name)
        if app_module is not None:
            setattr(app_module, "_spina_dash__norm_lt", normalize_loan_type)
    except Exception:
        pass


def install_dashboard_feature(
    app_class: type | None,
    *,
    log_exc: LogCallback | None = None,
    log_suppressed_once: SuppressedLogCallback | None = None,
) -> bool:
    """Install the complete dashboard on the desktop ``App`` class.

    The installer is idempotent and preserves the final behavior of the previous
    Wave 28 and v17-v20 monkey-patch chain.
    """
    if app_class is None:
        return False

    # Cash Control and statement fallback code still reads this historical global.
    # Install it even when the Dashboard methods were already wired previously.
    _install_compatibility_globals(app_class)

    if bool(getattr(app_class, "_spina_dashboard_wave76_installed", False)):
        return True

    def dashboard_log(context: str, exc: BaseException | None = None) -> None:
        _safe_log(log_exc, context, exc)

    try:
        configure_dashboard_chart_dependencies(
            {
                "_log_exc": dashboard_log,
                "_spina_v18_dashboard_palette": _spina_v18_dashboard_palette,
                "_spina_v18_draw_round_rect": _spina_v18_draw_round_rect,
                "_spina_v18_fmt_money_compact": _spina_v18_fmt_money_compact,
                "_spina_v18_patch_dashboard_chart_cards": _spina_v18_patch_dashboard_chart_cards,
                "_spina_v20_dash_palette": _spina_v20_dash_palette,
                "_spina_v20_money": _spina_v18_fmt_money_compact,
                "_spina_v20_round_rect": _spina_v20_round_rect,
            }
        )
        configure_legacy_dashboard_feature(
            fetch_rows=lambda app: fetch_dashboard_rows(app, log_exc=dashboard_log),
            log_exc=dashboard_log,
            draw_v18_charts=_spina_v18_draw_dashboard_charts,
            draw_v20_charts=_spina_v20_draw_dashboard_charts,
        )

        # Final effective methods after the old Wave 28 and v17-v20 patch chain.
        app_class._build_dashboard_tab = _spina_v17_build_dashboard_tab
        app_class.refresh_dashboard = _spina_v20_refresh_dashboard
        app_class._populate_dashboard_tree = _spina_v20_populate_dashboard_tree
        app_class._dashboard_visible_rows = _spina_v19_visible_dashboard_rows
        app_class._dashboard_fetch_rows = fetch_dashboard_rows

        original_apply_theme = getattr(app_class, "_apply_ui_theme", None)
        if callable(original_apply_theme):
            def apply_theme_with_dashboard(self, style=None):
                result = original_apply_theme(self, style)
                try:
                    _spina_configure_dashboard_tree_theme(self)
                except Exception:
                    pass
                return result

            app_class._apply_ui_theme = apply_theme_with_dashboard

        original_init = app_class.__init__

        def init_with_dashboard(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            try:
                self._build_dashboard_tab()
                _spina_apply_dashboard_role(self)
            except Exception as exc:
                dashboard_log("dashboard.init_hook", exc)

        app_class.__init__ = init_with_dashboard

        original_apply_role = getattr(app_class, "apply_role_access", None)
        if callable(original_apply_role):
            def apply_role_with_dashboard(self, *args, **kwargs):
                result = original_apply_role(self, *args, **kwargs)
                try:
                    _spina_apply_dashboard_role(self)
                except Exception:
                    pass
                return result

            app_class.apply_role_access = apply_role_with_dashboard

        original_mode_change = getattr(app_class, "_on_mode_change", None)
        if callable(original_mode_change):
            def mode_change_with_dashboard(self, *args, **kwargs):
                result = original_mode_change(self, *args, **kwargs)
                # Preserve the old two-stage behavior: refresh first, then align
                # the dashboard loan filter with the global Regular/7x7 switch.
                try:
                    self.refresh_dashboard()
                except Exception:
                    pass
                try:
                    mode = _mode_text(self)
                    filter_var = getattr(self, "dashboard_loan_filter_var", None)
                    if filter_var is not None and hasattr(filter_var, "set"):
                        filter_var.set("7x7" if "7" in mode else "Regular")
                    self._populate_dashboard_tree()
                except Exception:
                    pass
                return result

            app_class._on_mode_change = mode_change_with_dashboard

        app_class._spina_dashboard_wave76_installed = True
        return True
    except Exception as exc:
        _safe_suppressed_log(
            log_suppressed_once,
            "dashboard_wave76_install_failed",
            "Wave 76 dashboard feature installation failed",
            exc,
        )
        dashboard_log("dashboard.wave76.install", exc)
        return False
