from __future__ import annotations

from tkinter import ttk

_DEFAULT_SETTINGS = {}


def _missing_dependency(*_args, **_kwargs):
    raise RuntimeError("Wave 72 theme dependencies were not configured")


load_settings = _missing_dependency
save_settings = _missing_dependency
_log_suppressed_once = _missing_dependency


def configure_theme_application_dependencies(namespace):
    """Connect the extracted legacy function to the foundation app globals."""
    global _DEFAULT_SETTINGS, load_settings, save_settings, _log_suppressed_once

    _DEFAULT_SETTINGS = namespace.get("_DEFAULT_SETTINGS", {})
    load_settings = namespace.get("load_settings", _missing_dependency)
    save_settings = namespace.get("save_settings", _missing_dependency)
    _log_suppressed_once = namespace.get("_log_suppressed_once", _missing_dependency)

    required = ("_DEFAULT_SETTINGS", "load_settings", "save_settings", "_log_suppressed_once")
    return [name for name in required if name not in namespace]


def set_theme(self, theme: str, persist: bool = True):
    # Persist + re-apply styles immediately
    t = "dark" if str(theme or "").strip().lower().startswith("d") else "light"

    if persist:
        try:
            s = load_settings()
        except Exception:
            s = dict(_DEFAULT_SETTINGS)
        try:
            s["ui_theme"] = t
            save_settings(s)
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0320', 'suppressed exception excpass_0320', __spina_exc)
            pass

    # Re-run style setup (handles ttk theme_use + fonts + palettes)
    try:
        self.ui_theme = t
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0321', 'suppressed exception excpass_0321', __spina_exc)
        pass
    try:
        self._setup_style()
    except Exception:
        # Fallback: apply palette only
        try:
            style = ttk.Style(self.root)
            self.ui_theme = t
            self._apply_ui_theme(style)
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0322', 'suppressed exception excpass_0322', __spina_exc)
            pass

    # Update toggle button text if it exists
    try:
        if getattr(self, "theme_btn", None) is not None:
            self.theme_btn.configure(text=self._theme_toggle_text())
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0323', 'suppressed exception excpass_0323', __spina_exc)
        pass

    # Apply modern top header colors/buttons too
    try:
        self._refresh_header_theme()
    except Exception as __spina_exc:
        _log_suppressed_once('modern_ui_pass_14971', 'modern UI header theme refresh skipped', __spina_exc)
        pass

    # Apply to plain tk widgets too
    try:
        self._apply_tk_theme_recursive(self.root)
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0324', 'suppressed exception excpass_0324', __spina_exc)
        pass
    try:
        self._refresh_modern_shell_theme()
    except Exception as __spina_exc:
        _log_suppressed_once('modern_ui_pass_14982', 'modern UI shell theme refresh skipped', __spina_exc)
        pass
