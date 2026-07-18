#!/usr/bin/env python3
"""Remove legacy Data Bank export controls from the SPINA source.

This is a manual local injector. It removes/hides the Data Bank export strip shown as:

- Exports
- Date Range Template
- JSONL Month
- Daily Excel Template

It intentionally does not change client notes, balances, 7x7, interest,
payment allocation, report math, collector routes, or database writes.
"""

from __future__ import annotations

from pathlib import Path

APP_FILE = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
DOC_FILE = Path("docs/code-issue-review.md")
START = "# --- BEGIN: SPINA REMOVE DATA BANK EXPORT CONTROLS ---"
END = "# --- END: SPINA REMOVE DATA BANK EXPORT CONTROLS ---"

STATIC_LABELS = (
    "Date Range Template",
    "JSONL Month",
    "Daily Excel Template",
)

BLOCK = r'''
# --- BEGIN: SPINA REMOVE DATA BANK EXPORT CONTROLS ---
# Data Bank export controls are intentionally removed from the UI/action layer:
# Exports, Date Range Template, JSONL Month, and Daily Excel Template.
# Notes, balances, 7x7, payment logic, report math, collector routes, and DB writes are untouched.
def _spina_normalize_databank_export_label(value):
    try:
        return " ".join(str(value or "").strip().lower().split())
    except Exception:
        return ""


_SPINA_DATABANK_EXPORT_BUTTON_LABELS = {
    "date range template",
    "jsonl month",
    "daily excel template",
}

_SPINA_DATABANK_EXPORT_ALL_LABELS = set(_SPINA_DATABANK_EXPORT_BUTTON_LABELS)
_SPINA_DATABANK_EXPORT_ALL_LABELS.add("exports")

_SPINA_DATABANK_EXPORT_CALLBACKS = {
    "date range template": (
        "export_range_template",
        "export_date_range_template",
        "export_data_bank_range_template",
        "create_date_range_template",
    ),
    "jsonl month": (
        "export_jsonl_month",
        "export_month_jsonl",
        "create_jsonl_month",
        "save_jsonl_month",
    ),
    "daily excel template": (
        "export_daily_excel_template",
        "create_daily_excel_template",
        "create_daily_collection_template",
        "export_daily_collection_template",
    ),
}


def _spina_databank_export_removed_message(action="Data Bank export control"):
    message = str(action) + " is removed from Data Bank."
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


def _spina_make_removed_databank_export_action(label):
    def _spina_removed_action(*args, **kwargs):
        _spina_databank_export_removed_message(label)
        return None
    _spina_removed_action.__name__ = "_spina_removed_" + str(label).lower().replace(" ", "_")
    return _spina_removed_action


def _spina_disable_databank_export_callbacks():
    for _spina_label, _spina_names in _SPINA_DATABANK_EXPORT_CALLBACKS.items():
        _spina_replacement = _spina_make_removed_databank_export_action(_spina_label.title())
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


def _spina_databank_widget_text(widget):
    for option in ("text",):
        try:
            value = widget.cget(option)
            normalized = _spina_normalize_databank_export_label(value)
            if normalized:
                return normalized
        except Exception:
            pass
    for attr in ("_text", "text", "_name"):
        try:
            value = getattr(widget, attr, "")
            normalized = _spina_normalize_databank_export_label(value)
            if normalized:
                return normalized
        except Exception:
            pass
    return ""


def _spina_remove_databank_export_widget(widget):
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


def _spina_parent_has_databank_export_buttons(widget):
    try:
        parent = widget.master
    except Exception:
        parent = None
    if parent is None:
        return False
    try:
        for child in parent.winfo_children():
            if _spina_databank_widget_text(child) in _SPINA_DATABANK_EXPORT_BUTTON_LABELS:
                return True
    except Exception:
        return False
    return False


def _spina_hide_databank_export_controls(root):
    removed = 0

    def _spina_walk(widget):
        nonlocal removed
        try:
            text = _spina_databank_widget_text(widget)
            should_remove = text in _SPINA_DATABANK_EXPORT_BUTTON_LABELS
            if text == "exports" and _spina_parent_has_databank_export_buttons(widget):
                should_remove = True
            if should_remove:
                removed += 1
                _spina_remove_databank_export_widget(widget)
                return
            for child in widget.winfo_children():
                _spina_walk(child)
        except Exception:
            pass

    try:
        _spina_walk(root)
    except Exception:
        pass
    return removed


def _spina_wrap_tk_geometry_for_databank_export_hide():
    try:
        import tkinter as _spina_tk
    except Exception:
        return

    def _spina_patch_method(_spina_cls, _spina_name):
        try:
            original = getattr(_spina_cls, _spina_name, None)
            if not callable(original) or getattr(original, "_spina_databank_export_geom_wrapped", False):
                return

            def _spina_wrapped(self, *args, **kwargs):
                result = original(self, *args, **kwargs)
                try:
                    text = _spina_databank_widget_text(self)
                    if text in _SPINA_DATABANK_EXPORT_BUTTON_LABELS or (
                        text == "exports" and _spina_parent_has_databank_export_buttons(self)
                    ):
                        try:
                            root = self.winfo_toplevel()
                            root.after(1, lambda w=self: _spina_remove_databank_export_widget(w))
                        except Exception:
                            _spina_remove_databank_export_widget(self)
                except Exception:
                    pass
                return result

            _spina_wrapped.__name__ = getattr(original, "__name__", _spina_name)
            _spina_wrapped._spina_databank_export_geom_wrapped = True
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


def _spina_schedule_databank_export_hide(root, attempts=160, delay_ms=250):
    try:
        _spina_hide_databank_export_controls(root)
    except Exception:
        pass
    try:
        if attempts > 0:
            root.after(delay_ms, lambda: _spina_schedule_databank_export_hide(root, attempts - 1, delay_ms))
    except Exception:
        pass


def _spina_bind_late_databank_export_hide(root):
    def _spina_rescan_later(event=None):
        try:
            for delay in (1, 25, 100, 300, 800, 1500):
                root.after(delay, lambda: _spina_hide_databank_export_controls(root))
        except Exception:
            pass

    for _spina_event in ("<ButtonRelease-1>", "<Button-1>", "<<NotebookTabChanged>>", "<Map>", "<Visibility>", "<FocusIn>"):
        try:
            root.bind_all(_spina_event, _spina_rescan_later, add="+")
        except Exception:
            pass


def _spina_wrap_databank_builders_for_export_hide():
    try:
        if "App" not in globals():
            return
        for _spina_method_name in (
            "_build_data_bank_tab",
            "build_data_bank_tab",
            "create_data_bank_tab",
            "setup_data_bank_tab",
            "_create_data_bank_tab",
            "refresh_data_grid",
            "show_data_bank_tab",
            "load_data_bank_tab",
        ):
            try:
                original = getattr(App, _spina_method_name, None)
                if not callable(original) or getattr(original, "_spina_databank_export_hide_wrapped", False):
                    continue

                def _spina_make_wrapped(_spina_original, _spina_name):
                    def _spina_wrapped(self, *args, **kwargs):
                        result = _spina_original(self, *args, **kwargs)
                        try:
                            for delay in (1, 25, 100, 300, 1000):
                                self.after(delay, lambda: _spina_hide_databank_export_controls(self))
                        except Exception:
                            _spina_hide_databank_export_controls(self)
                        return result
                    _spina_wrapped.__name__ = getattr(_spina_original, "__name__", _spina_name)
                    _spina_wrapped._spina_databank_export_hide_wrapped = True
                    return _spina_wrapped

                setattr(App, _spina_method_name, _spina_make_wrapped(original, _spina_method_name))
            except Exception:
                pass
    except Exception:
        pass


_spina_disable_databank_export_callbacks()
_spina_wrap_tk_geometry_for_databank_export_hide()
_spina_wrap_databank_builders_for_export_hide()

try:
    _spina_original_app_init_for_databank_exports = App.__init__
    if not getattr(_spina_original_app_init_for_databank_exports, "_spina_databank_exports_removed", False):
        def _spina_app_init_without_databank_exports(self, *args, **kwargs):
            result = _spina_original_app_init_for_databank_exports(self, *args, **kwargs)
            _spina_disable_databank_export_callbacks()
            _spina_wrap_tk_geometry_for_databank_export_hide()
            _spina_wrap_databank_builders_for_export_hide()
            try:
                _spina_bind_late_databank_export_hide(self)
            except Exception:
                pass
            try:
                for delay in (1, 25, 50, 100, 250, 500, 1000, 2500, 5000):
                    self.after(delay, lambda: _spina_hide_databank_export_controls(self))
                _spina_schedule_databank_export_hide(self)
            except Exception:
                _spina_hide_databank_export_controls(self)
            return result

        _spina_app_init_without_databank_exports.__name__ = getattr(
            _spina_original_app_init_for_databank_exports, "__name__", "__init__"
        )
        _spina_app_init_without_databank_exports._spina_databank_exports_removed = True
        App.__init__ = _spina_app_init_without_databank_exports
except Exception:
    pass
# --- END: SPINA REMOVE DATA BANK EXPORT CONTROLS ---
'''.strip()

DOC_NOTE = """

## Phase 6 remove Data Bank export controls

The Data Bank export controls are removed from the UI/action layer:
Exports, Date Range Template, JSONL Month, and Daily Excel Template.

Safety rules for this phase:

- no notes storage or note rendering logic is changed
- no Collector Route Daily Ledger logic is changed
- no Client Statement PDF logic is changed
- no loan, balance, 7x7, interest, payment allocation, or report math is changed
- visible Data Bank export widgets are hidden/destroyed if they are created dynamically
"""


def remove_existing_block(text: str) -> str:
    while True:
        start = text.find(START)
        if start == -1:
            return text
        end = text.find(END, start)
        if end == -1:
            raise SystemExit("Found Data Bank export removal block start without end marker")
        end += len(END)
        text = text[:start].rstrip() + "\n\n" + text[end:].lstrip()


def _contains_static_label(line: str) -> bool:
    lowered = line.lower()
    return any(label.lower() in lowered for label in STATIC_LABELS)


def _looks_like_ui_line(line: str) -> bool:
    lowered = line.lower()
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


def remove_static_export_lines(source: str) -> tuple[str, int]:
    lines = source.splitlines()
    removed = 0
    for index, line in enumerate(lines):
        if _contains_static_label(line) and _looks_like_ui_line(line):
            indent = line[: len(line) - len(line.lstrip())]
            lines[index] = indent + "# SPINA removed Data Bank export control statement"
            removed += 1
    return "\n".join(lines) + ("\n" if source.endswith("\n") else ""), removed


def main() -> int:
    print("Starting Data Bank export control remover...", flush=True)
    if not APP_FILE.exists():
        raise SystemExit(f"App file not found: {APP_FILE}")

    print("Reading SPINA app file...", flush=True)
    source = APP_FILE.read_text(encoding="utf-8")
    source = remove_existing_block(source)
    source, static_removed = remove_static_export_lines(source)

    marker = 'if __name__ == "__main__":'
    pos = source.rfind(marker)
    if pos == -1:
        marker = "if __name__ == '__main__':"
        pos = source.rfind(marker)
    if pos == -1:
        raise SystemExit("Could not find __main__ guard for insertion")

    print("Inserting runtime removal block...", flush=True)
    source = source[:pos].rstrip() + "\n\n" + BLOCK + "\n\n" + source[pos:].lstrip()
    APP_FILE.write_text(source, encoding="utf-8")

    if DOC_FILE.exists():
        doc = DOC_FILE.read_text(encoding="utf-8")
        if "## Phase 6 remove Data Bank export controls" not in doc:
            DOC_FILE.write_text(doc.rstrip() + DOC_NOTE, encoding="utf-8")

    print(f"Data Bank export controls removal block inserted. Static lines removed: {static_removed}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
