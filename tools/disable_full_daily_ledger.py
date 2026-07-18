#!/usr/bin/env python3
"""Fast remover for legacy Clients-tab action buttons in SPINA.

Targets these exact legacy button labels:
- From Transactions
- Full Ledger
- Export Template
- Import Excel

The tool is intentionally narrow. It does not change collector route printing,
notes, payments, balances, 7x7, interest, report math, or database writes.
"""

from __future__ import annotations

from pathlib import Path

APP_FILE = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
DOC_FILE = Path("docs/code-issue-review.md")
START = "# --- BEGIN: SPINA REMOVE LEGACY CLIENT ACTION BUTTONS ---"
END = "# --- END: SPINA REMOVE LEGACY CLIENT ACTION BUTTONS ---"

LEGACY_LABELS = (
    "From Transactions",
    "Full Ledger",
    "Export Template",
    "Import Excel",
)

LEGACY_LABELS_LOWER = tuple(label.lower() for label in LEGACY_LABELS)

BLOCK = r'''
# --- BEGIN: SPINA REMOVE LEGACY CLIENT ACTION BUTTONS ---
# Legacy Clients-tab actions are intentionally removed from the UI/action layer:
# From Transactions, Full Ledger, Export Template, and Import Excel.
# Collector Route, notes, balances, 7x7, payment logic, and report math are untouched.
def _spina_legacy_client_action_removed_message(action="Legacy client action"):
    message = str(action) + " is removed from the Clients tab."
    try:
        if "messagebox" in globals():
            messagebox.showinfo("Action Removed", message)
        else:
            print("[SPINA] " + message, flush=True)
    except Exception:
        try:
            print("[SPINA] " + message, flush=True)
        except Exception:
            pass


def _spina_make_removed_legacy_client_action(label):
    def _spina_removed_action(*args, **kwargs):
        _spina_legacy_client_action_removed_message(label)
        return None
    _spina_removed_action.__name__ = "_spina_removed_" + str(label).lower().replace(" ", "_")
    return _spina_removed_action


def _spina_normalize_legacy_label(value):
    try:
        return " ".join(str(value or "").strip().lower().split())
    except Exception:
        return ""


_SPINA_LEGACY_CLIENT_LABELS = {
    "from transactions",
    "full ledger",
    "full daily ledger",
    "export template",
    "import excel",
}

_SPINA_LEGACY_CLIENT_CALLBACKS = {
    "from transactions": (
        "from_transactions",
        "load_from_transactions",
        "refresh_from_transactions",
        "import_from_transactions",
        "sync_from_transactions",
        "attach_direct_integration",
        "_maybe_suggest_link_clients",
    ),
    "full ledger": (
        "print_full_daily_ledger",
        "generate_full_daily_ledger",
        "open_full_daily_ledger",
        "_print_full_daily_ledger",
    ),
    "export template": (
        "export_range_template",
        "export_daily_collection_template",
        "export_clients_template",
        "_export_clients_template",
    ),
    "import excel": (
        "import_clients_from_excel",
        "_app_import_clients_from_excel",
        "_import_clients_from_excel",
        "import_clients_excel",
    ),
}


def _spina_disable_legacy_client_callbacks():
    for _spina_label, _spina_names in _SPINA_LEGACY_CLIENT_CALLBACKS.items():
        _spina_replacement = _spina_make_removed_legacy_client_action(_spina_label.title())
        for _spina_name in _spina_names:
            try:
                if callable(globals().get(_spina_name)):
                    globals()[_spina_name] = _spina_replacement
            except Exception:
                pass
            try:
                if "App" in globals() and hasattr(App, _spina_name):
                    setattr(App, _spina_name, _spina_replacement)
            except Exception:
                pass


def _spina_widget_text(widget):
    for option in ("text",):
        try:
            normalized = _spina_normalize_legacy_label(widget.cget(option))
            if normalized:
                return normalized
        except Exception:
            pass
    for attr in ("_text", "text", "_name"):
        try:
            normalized = _spina_normalize_legacy_label(getattr(widget, attr, ""))
            if normalized:
                return normalized
        except Exception:
            pass
    return ""


def _spina_remove_widget(widget):
    try:
        widget.configure(state="disabled")
    except Exception:
        pass
    try:
        widget.pack_forget()
    except Exception:
        pass
    try:
        widget.grid_remove()
    except Exception:
        pass
    try:
        widget.place_forget()
    except Exception:
        pass
    try:
        widget.destroy()
    except Exception:
        pass


def _spina_hide_legacy_client_action_widgets(root):
    removed = 0

    def _spina_hide_widget(widget):
        nonlocal removed
        try:
            if _spina_widget_text(widget) in _SPINA_LEGACY_CLIENT_LABELS:
                removed += 1
                _spina_remove_widget(widget)
                return
            for child in widget.winfo_children():
                _spina_hide_widget(child)
        except Exception:
            pass

    try:
        _spina_hide_widget(root)
    except Exception:
        pass
    return removed


def _spina_schedule_legacy_client_button_hide(root, attempts=240, delay_ms=250):
    try:
        _spina_hide_legacy_client_action_widgets(root)
    except Exception:
        pass
    try:
        if attempts > 0:
            root.after(delay_ms, lambda: _spina_schedule_legacy_client_button_hide(root, attempts - 1, delay_ms))
    except Exception:
        pass


def _spina_bind_late_legacy_client_button_hide(root):
    def _spina_rescan_later(event=None):
        try:
            for delay in (1, 25, 100, 300, 800, 1500):
                root.after(delay, lambda: _spina_hide_legacy_client_action_widgets(root))
        except Exception:
            pass

    for _spina_event in ("<ButtonRelease-1>", "<Button-1>", "<<NotebookTabChanged>>", "<Map>", "<Visibility>", "<FocusIn>"):
        try:
            root.bind_all(_spina_event, _spina_rescan_later, add="+")
        except Exception:
            pass


def _spina_wrap_tk_geometry_for_legacy_button_hide():
    try:
        import tkinter as _spina_tk
    except Exception:
        return

    def _spina_patch_method(_spina_cls, _spina_name):
        try:
            original = getattr(_spina_cls, _spina_name, None)
            if not callable(original) or getattr(original, "_spina_legacy_button_geom_wrapped", False):
                return

            def _spina_wrapped(self, *args, **kwargs):
                result = original(self, *args, **kwargs)
                try:
                    if _spina_widget_text(self) in _SPINA_LEGACY_CLIENT_LABELS:
                        try:
                            self.winfo_toplevel().after(1, lambda w=self: _spina_remove_widget(w))
                        except Exception:
                            _spina_remove_widget(self)
                except Exception:
                    pass
                return result

            _spina_wrapped.__name__ = getattr(original, "__name__", _spina_name)
            _spina_wrapped._spina_legacy_button_geom_wrapped = True
            setattr(_spina_cls, _spina_name, _spina_wrapped)
        except Exception:
            pass

    for _spina_cls_name, _spina_method_names in (
        ("Pack", ("pack", "pack_configure")),
        ("Grid", ("grid", "grid_configure")),
        ("Place", ("place", "place_configure")),
        ("Misc", ("configure", "config")),
    ):
        try:
            _spina_cls = getattr(_spina_tk, _spina_cls_name, None)
            if _spina_cls is None:
                continue
            for _spina_method_name in _spina_method_names:
                _spina_patch_method(_spina_cls, _spina_method_name)
        except Exception:
            pass


def _spina_wrap_client_tab_builders_for_legacy_button_hide():
    try:
        if "App" not in globals():
            return
        for _spina_method_name in (
            "_build_clients_tab",
            "build_clients_tab",
            "create_clients_tab",
            "setup_clients_tab",
            "_create_clients_tab",
            "refresh_clients",
            "_refresh_clients",
            "show_clients_tab",
            "load_clients_tab",
        ):
            try:
                original = getattr(App, _spina_method_name, None)
                if not callable(original) or getattr(original, "_spina_legacy_button_hide_wrapped", False):
                    continue

                def _spina_make_wrapped(_spina_original, _spina_name):
                    def _spina_wrapped(self, *args, **kwargs):
                        result = _spina_original(self, *args, **kwargs)
                        try:
                            for delay in (1, 25, 100, 300, 1000):
                                self.after(delay, lambda: _spina_hide_legacy_client_action_widgets(self))
                        except Exception:
                            _spina_hide_legacy_client_action_widgets(self)
                        return result
                    _spina_wrapped.__name__ = getattr(_spina_original, "__name__", _spina_name)
                    _spina_wrapped._spina_legacy_button_hide_wrapped = True
                    return _spina_wrapped

                setattr(App, _spina_method_name, _spina_make_wrapped(original, _spina_method_name))
            except Exception:
                pass
    except Exception:
        pass


_spina_disable_legacy_client_callbacks()
_spina_wrap_tk_geometry_for_legacy_button_hide()
_spina_wrap_client_tab_builders_for_legacy_button_hide()

try:
    _spina_original_app_init_for_legacy_client_buttons = App.__init__
    if not getattr(_spina_original_app_init_for_legacy_client_buttons, "_spina_legacy_client_buttons_removed", False):
        def _spina_app_init_without_legacy_client_buttons(self, *args, **kwargs):
            result = _spina_original_app_init_for_legacy_client_buttons(self, *args, **kwargs)
            _spina_disable_legacy_client_callbacks()
            _spina_wrap_tk_geometry_for_legacy_button_hide()
            _spina_wrap_client_tab_builders_for_legacy_button_hide()
            try:
                _spina_bind_late_legacy_client_button_hide(self)
            except Exception:
                pass
            try:
                for delay in (1, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000):
                    self.after(delay, lambda: _spina_hide_legacy_client_action_widgets(self))
                _spina_schedule_legacy_client_button_hide(self)
            except Exception:
                _spina_hide_legacy_client_action_widgets(self)
            return result

        _spina_app_init_without_legacy_client_buttons.__name__ = getattr(
            _spina_original_app_init_for_legacy_client_buttons, "__name__", "__init__"
        )
        _spina_app_init_without_legacy_client_buttons._spina_legacy_client_buttons_removed = True
        App.__init__ = _spina_app_init_without_legacy_client_buttons
except Exception:
    pass
# --- END: SPINA REMOVE LEGACY CLIENT ACTION BUTTONS ---
'''.strip()

DOC_NOTE = """

## Phase 5 remove legacy Clients-tab actions

The legacy Clients-tab action buttons are removed from the UI/action layer:
From Transactions, Full Ledger, Export Template, and Import Excel.

Safety rules for this phase:

- no notes storage or note rendering logic is changed
- no Collector Route Daily Ledger logic is changed
- no loan, balance, 7x7, interest, payment allocation, or report math is changed
- exact legacy button creation statements are removed when found in the source
- old known callback entry points show a removed-action message instead of running
- visible legacy client action widgets are hidden/destroyed if they are created dynamically
"""


def _flush(message: str) -> None:
    print(message, flush=True)


def remove_existing_blocks(text: str) -> str:
    markers = [
        ("# --- BEGIN: SPINA DISABLE FULL DAILY LEDGER ---", "# --- END: SPINA DISABLE FULL DAILY LEDGER ---"),
        (START, END),
    ]
    for start_marker, end_marker in markers:
        while True:
            start = text.find(start_marker)
            if start == -1:
                break
            end = text.find(end_marker, start)
            if end == -1:
                raise SystemExit(f"Found block start without end marker: {start_marker}")
            end += len(end_marker)
            text = text[:start].rstrip() + "\n\n" + text[end:].lstrip()
    return text


def _contains_legacy_label(line: str) -> bool:
    lowered = line.lower()
    return any(label in lowered for label in LEGACY_LABELS_LOWER)


def _looks_like_legacy_button_line(line: str) -> bool:
    lowered = line.lower()
    if not _contains_legacy_label(line):
        return False
    ui_terms = (
        "button",
        "ctkbutton",
        "ttk.button",
        "tk.button",
        "command=",
        "menu.add_command",
        "add_command",
    )
    return any(term in lowered for term in ui_terms)


def remove_static_legacy_button_lines(source: str) -> tuple[str, int]:
    lines = source.splitlines()
    removed = 0
    for idx, line in enumerate(lines):
        if _looks_like_legacy_button_line(line):
            indent = line[: len(line) - len(line.lstrip())]
            lines[idx] = indent + "# SPINA removed legacy Clients-tab action button statement"
            removed += 1
    return "\n".join(lines) + ("\n" if source.endswith("\n") else ""), removed


def main() -> int:
    _flush("Starting legacy Clients-tab action remover...")
    if not APP_FILE.exists():
        raise SystemExit(f"App file not found: {APP_FILE}")

    _flush("Reading SPINA app file...")
    source = APP_FILE.read_text(encoding="utf-8")

    _flush("Removing old injected blocks...")
    source = remove_existing_blocks(source)

    _flush("Scanning for exact legacy button lines...")
    source, static_removed = remove_static_legacy_button_lines(source)

    marker = 'if __name__ == "__main__":'
    pos = source.rfind(marker)
    if pos == -1:
        marker = "if __name__ == '__main__':"
        pos = source.rfind(marker)
    if pos == -1:
        raise SystemExit("Could not find __main__ guard for insertion")

    _flush("Inserting runtime removal fallback...")
    source = source[:pos].rstrip() + "\n\n" + BLOCK + "\n\n" + source[pos:].lstrip()

    _flush("Writing updated SPINA app file...")
    APP_FILE.write_text(source, encoding="utf-8")

    if DOC_FILE.exists():
        doc = DOC_FILE.read_text(encoding="utf-8")
        if "## Phase 5 remove legacy Clients-tab actions" not in doc:
            DOC_FILE.write_text(doc.rstrip() + DOC_NOTE, encoding="utf-8")

    _flush(f"Done. Static legacy button lines removed: {static_removed}")
    _flush("Now run: python -m py_compile \"OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
