"""Complete Collector Route feature installer for SPINA Wave 79."""
from __future__ import annotations

from typing import Any, Mapping

from spina_app import collector_route_controller as _controller
from spina_app import collector_route_report as _report
from spina_app.collector_dialog_presentation import (
    configure_collector_dialog_dependencies,
    _spina_v27_collector_editor_dialog,
)
from spina_app.collector_refresh_presentation import (
    configure_collector_refresh_dependencies,
    refresh_collectors as _refresh_collectors,
)
from spina_app.collector_tab_presentation import (
    configure_collector_tab_dependencies,
    _spina_v27_build_collectors_tab,
)
from spina_app.tabs.collector_route import (
    configure_collector_route_dependencies,
    _spina_v27_hidden_collector_widgets,
    _spina_v27_update_route_cards,
)
from spina_app import tabs as _tabs_package
from spina_app.tabs import collectors as _editor
from spina_app.theme_palettes import _spina_v25_collector_colors

_EDITOR_METHOD_NAMES = (
    "_collectors_get_selected_name",
    "_collectors_toggle_sections",
    "_collectors_apply_markers",
    "_collectors_refresh_bulk_bar",
    "_collectors_clear_checked",
    "_collectors_start_inline_edit",
    "_collectors_load_inline_edit_fields",
    "_collectors_cancel_inline_edit",
    "_collectors_choose_areas",
    "_collectors_add_area_text",
    "_collectors_remove_area",
    "_collectors_move_area",
)


def _safe_log(callback, context, exc=None):
    if not callable(callback):
        return
    try:
        callback(context, exc)
    except Exception:
        pass


def _selected_collector(self, *_args, **_kwargs):
    """Final lightweight v27 selection behavior; the visible right panel stays removed."""
    name = ""
    try:
        tree = getattr(self, "collectors_tree", None)
        selected = tree.selection() if tree is not None else ()
        if selected:
            values = tree.item(selected[0], "values") or ()
            name = self._collectors_name_from_values(values)
    except Exception:
        name = ""
    try:
        self._selected_collector_name = str(name or "").strip()
    except Exception:
        pass
    try:
        if name and hasattr(self, "collector_route_table_status_var"):
            self.collector_route_table_status_var.set(f"Selected: {name}")
    except Exception:
        pass
    try:
        _spina_v27_update_route_cards(self)
    except Exception:
        pass
    return None


def install_collector_route_feature(
    app_class: type | None,
    *,
    namespace: Mapping[str, Any],
    log_exc=None,
    log_suppressed_once=None,
) -> bool:
    """Bind the complete Collector Route architecture exactly once."""
    if app_class is None:
        return False
    if bool(getattr(app_class, "_spina_collector_route_wave79_installed", False)):
        return True
    try:
        dependencies = dict(namespace)
        dependencies.update(
            {
                "_spina_v27_route_colors": _spina_v25_collector_colors,
                "_spina_v27_hidden_collector_widgets": _spina_v27_hidden_collector_widgets,
                "_spina_v27_update_route_cards": _spina_v27_update_route_cards,
                "_spina_v27_build_collectors_tab": _spina_v27_build_collectors_tab,
            }
        )
        configure_collector_route_dependencies(dependencies)
        configure_collector_dialog_dependencies(dependencies)
        configure_collector_refresh_dependencies(dependencies)
        configure_collector_tab_dependencies(dependencies)
        _controller.configure_collector_route_controller_dependencies(dependencies)
        _report.configure_collector_route_report_dependencies(dependencies)

        app_class._build_collectors_tab = _spina_v27_build_collectors_tab
        app_class._collector_editor_dialog = _spina_v27_collector_editor_dialog

        for name in _EDITOR_METHOD_NAMES:
            value = getattr(_editor, name, None)
            if callable(value):
                setattr(app_class, name, value)
        for name in _controller.COLLECTOR_ROUTE_METHOD_NAMES:
            value = getattr(_controller, name, None)
            if callable(value):
                setattr(app_class, name, value)
        for name in _report.COLLECTOR_ROUTE_METHOD_NAMES:
            value = getattr(_report, name, None)
            if callable(value):
                setattr(app_class, name, value)

        def refresh_with_cards(self, *args, **kwargs):
            result = _refresh_collectors(self, *args, **kwargs)
            try:
                _spina_v27_update_route_cards(self)
            except Exception:
                pass
            return result

        app_class.refresh_collectors = refresh_with_cards
        app_class._on_collectors_select = _selected_collector
        app_class._spina_collector_route_wave79_installed = True
        return True
    except Exception as exc:
        try:
            if callable(log_suppressed_once):
                log_suppressed_once(
                    "collector_route_wave79_install_failed",
                    "Wave 79 Collector Route installation failed",
                    exc,
                )
        except Exception:
            pass
        _safe_log(log_exc, "collector_route.wave79.install", exc)
        return False
