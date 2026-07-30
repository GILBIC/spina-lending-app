"""Final side-navigation runtime ownership for SPINA Wave 86."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable

from spina_app.side_navigation_presentation import (
    configure_side_navigation_dependencies,
    _spina_v13_apply_ui_theme,
    _spina_v13_hide_main_notebook_tabs,
    _spina_v13_rebuild_side_nav,
    _spina_v13_refresh_side_nav_selection,
    _spina_v13_setup_style,
    _spina_v13_side_nav_items,
)

SuppressedLogCallback = Callable[[str, str, BaseException | None], Any]


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


def _pick_original(
    app_class: type,
    namespace: Mapping[str, object],
    *names: str,
    fallback_attr: str,
):
    for name in names:
        candidate = namespace.get(name)
        if callable(candidate):
            return candidate
    candidate = getattr(app_class, fallback_attr, None)
    return candidate if callable(candidate) else None


def install_side_navigation_feature(
    app_class: type | None,
    *,
    namespace: Mapping[str, object] | None = None,
    log_suppressed_once: SuppressedLogCallback | None = None,
) -> bool:
    """Install one final sidebar boundary after all legacy wrappers have loaded."""
    if app_class is None:
        return False

    dependencies = dict(namespace or {})
    configure_side_navigation_dependencies(dependencies)

    if bool(getattr(app_class, "_spina_side_navigation_wave86_installed", False)):
        return True

    original_setup = _pick_original(
        app_class,
        dependencies,
        "_spina_v13_orig_setup_style",
        fallback_attr="_setup_style",
    )
    original_theme = _pick_original(
        app_class,
        dependencies,
        "_spina_v13_orig_apply_theme",
        fallback_attr="_apply_ui_theme",
    )
    original_init = _pick_original(
        app_class,
        dependencies,
        "_spina_v13_orig_init",
        fallback_attr="__init__",
    )
    original_role = _pick_original(
        app_class,
        dependencies,
        "_spina_orig_apply_role_modern_sidebar",
        "_spina_v13_orig_apply_role",
        fallback_attr="apply_role_access",
    )

    if not callable(original_init):
        return False

    app_class._spina_side_navigation_wave86_original_init = original_init
    app_class._spina_side_navigation_wave86_original_setup_style = original_setup
    app_class._spina_side_navigation_wave86_original_apply_theme = original_theme
    app_class._spina_side_navigation_wave86_original_apply_role = original_role

    app_class._side_nav_items = _spina_v13_side_nav_items
    app_class._rebuild_side_nav = _spina_v13_rebuild_side_nav
    app_class._refresh_side_nav_selection = _spina_v13_refresh_side_nav_selection
    app_class._hide_main_notebook_tabs = _spina_v13_hide_main_notebook_tabs

    if callable(original_setup):

        def setup_style_with_side_navigation(self, *args, **kwargs):
            result = original_setup(self, *args, **kwargs)
            try:
                self._hide_main_notebook_tabs()
            except Exception as exc:
                _safe_suppressed_log(
                    log_suppressed_once,
                    "side_navigation_wave86_setup",
                    "Wave 86 sidebar setup refresh failed",
                    exc,
                )
            return result

        app_class._setup_style = setup_style_with_side_navigation

    if callable(original_theme):

        def apply_theme_with_side_navigation(self, *args, **kwargs):
            result = original_theme(self, *args, **kwargs)
            try:
                self._hide_main_notebook_tabs()
                self._rebuild_side_nav()
            except Exception as exc:
                _safe_suppressed_log(
                    log_suppressed_once,
                    "side_navigation_wave86_theme",
                    "Wave 86 sidebar theme refresh failed",
                    exc,
                )
            return result

        app_class._apply_ui_theme = apply_theme_with_side_navigation

    def init_with_side_navigation(self, *args, **kwargs):
        # Startup cancellation must escape before any sidebar post-init work.
        original_init(self, *args, **kwargs)
        try:
            self._hide_main_notebook_tabs()
            self._rebuild_side_nav()
        except Exception as exc:
            _safe_suppressed_log(
                log_suppressed_once,
                "side_navigation_wave86_init",
                "Wave 86 sidebar initialization failed",
                exc,
            )

    app_class.__init__ = init_with_side_navigation

    if callable(original_role):

        def apply_role_with_side_navigation(self, *args, **kwargs):
            result = original_role(self, *args, **kwargs)
            try:
                self._hide_main_notebook_tabs()
                self._rebuild_side_nav()
            except Exception as exc:
                _safe_suppressed_log(
                    log_suppressed_once,
                    "side_navigation_wave86_role",
                    "Wave 86 sidebar role refresh failed",
                    exc,
                )
            return result

        app_class.apply_role_access = apply_role_with_side_navigation

    app_class._spina_side_navigation_wave86_installed = True
    return all(
        callable(getattr(app_class, name, None))
        for name in (
            "_side_nav_items",
            "_rebuild_side_nav",
            "_refresh_side_nav_selection",
            "_hide_main_notebook_tabs",
            "__init__",
        )
    )
