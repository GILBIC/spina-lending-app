#!/usr/bin/env python3
"""Disable the Full Daily Ledger action in the SPINA source.

This is intentionally behavior-limited. It does not delete report code, change
collector-route printing, or touch note/payment/balance logic. It only inserts a
small runtime override that hides/disables Full Daily Ledger UI entries and makes
old Full Daily Ledger callbacks show a disabled message.
"""

from __future__ import annotations

from pathlib import Path

APP_FILE = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
DOC_FILE = Path("docs/code-issue-review.md")
START = "# --- BEGIN: SPINA DISABLE FULL DAILY LEDGER ---"
END = "# --- END: SPINA DISABLE FULL DAILY LEDGER ---"

BLOCK = r'''
# --- BEGIN: SPINA DISABLE FULL DAILY LEDGER ---
# Full Daily Ledger is intentionally disabled from the UI.
# Collector Route Daily Ledger remains available and note handling is untouched.
def _spina_full_daily_ledger_disabled_message():
    message = "Full Daily Ledger is disabled. Use Collector Route Daily Ledger instead."
    try:
        if "messagebox" in globals():
            messagebox.showinfo("Full Daily Ledger Disabled", message)
        else:
            print("[SPINA] " + message, flush=True)
    except Exception:
        try:
            print("[SPINA] " + message, flush=True)
        except Exception:
            pass


def _spina_disabled_full_daily_ledger(*args, **kwargs):
    _spina_full_daily_ledger_disabled_message()
    return None


def _spina_disable_full_daily_ledger_callbacks():
    for _spina_name in (
        "print_full_daily_ledger",
        "generate_full_daily_ledger",
        "open_full_daily_ledger",
        "_print_full_daily_ledger",
    ):
        try:
            if callable(globals().get(_spina_name)):
                globals()[_spina_name] = _spina_disabled_full_daily_ledger
        except Exception:
            pass
    try:
        _spina_app_methods = (
            "print_full_daily_ledger",
            "generate_full_daily_ledger",
            "open_full_daily_ledger",
            "_print_full_daily_ledger",
        )
        for _spina_method in _spina_app_methods:
            try:
                if hasattr(App, _spina_method):
                    setattr(App, _spina_method, _spina_disabled_full_daily_ledger)
            except Exception:
                pass
    except Exception:
        pass


def _spina_hide_full_daily_ledger_widgets(root):
    needle = "full daily ledger"

    def _spina_hide_widget(widget):
        try:
            text = ""
            try:
                text = str(widget.cget("text") or "")
            except Exception:
                text = ""
            if needle in text.lower():
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
            for child in widget.winfo_children():
                _spina_hide_widget(child)
        except Exception:
            pass

    try:
        _spina_hide_widget(root)
    except Exception:
        pass


_spina_disable_full_daily_ledger_callbacks()

try:
    _spina_original_app_init_for_full_ledger_disable = App.__init__
    if not getattr(_spina_original_app_init_for_full_ledger_disable, "_spina_full_ledger_disable_wrapped", False):
        def _spina_app_init_with_full_ledger_disabled(self, *args, **kwargs):
            result = _spina_original_app_init_for_full_ledger_disable(self, *args, **kwargs)
            _spina_disable_full_daily_ledger_callbacks()
            try:
                self.after(250, lambda: _spina_hide_full_daily_ledger_widgets(self))
                self.after(1000, lambda: _spina_hide_full_daily_ledger_widgets(self))
            except Exception:
                _spina_hide_full_daily_ledger_widgets(self)
            return result

        _spina_app_init_with_full_ledger_disabled.__name__ = getattr(
            _spina_original_app_init_for_full_ledger_disable, "__name__", "__init__"
        )
        _spina_app_init_with_full_ledger_disabled._spina_full_ledger_disable_wrapped = True
        App.__init__ = _spina_app_init_with_full_ledger_disabled
except Exception:
    pass
# --- END: SPINA DISABLE FULL DAILY LEDGER ---
'''.strip()

DOC_NOTE = """

## Phase 5 disable Full Daily Ledger action

Full Daily Ledger is disabled from the UI/action layer. This does not delete old
report code directly. Collector Route Daily Ledger stays available.

Safety rules for this phase:

- no notes storage or note rendering logic is changed
- no loan, balance, 7x7, interest, payment allocation, or report math is changed
- old Full Daily Ledger callbacks show a disabled message instead of printing
- visible Full Daily Ledger widgets are hidden/disabled after the app opens
"""


def remove_existing_block(text: str) -> str:
    start = text.find(START)
    if start == -1:
        return text
    end = text.find(END, start)
    if end == -1:
        raise SystemExit("Found Full Daily Ledger disable block start without end marker")
    end += len(END)
    return text[:start].rstrip() + "\n\n" + text[end:].lstrip()


def main() -> int:
    if not APP_FILE.exists():
        raise SystemExit(f"App file not found: {APP_FILE}")
    source = APP_FILE.read_text(encoding="utf-8")
    source = remove_existing_block(source)

    marker = 'if __name__ == "__main__":'
    pos = source.rfind(marker)
    if pos == -1:
        marker = "if __name__ == '__main__':"
        pos = source.rfind(marker)
    if pos == -1:
        raise SystemExit("Could not find __main__ guard for insertion")

    source = source[:pos].rstrip() + "\n\n" + BLOCK + "\n\n" + source[pos:].lstrip()
    APP_FILE.write_text(source, encoding="utf-8")

    if DOC_FILE.exists():
        doc = DOC_FILE.read_text(encoding="utf-8")
        if "## Phase 5 disable Full Daily Ledger action" not in doc:
            DOC_FILE.write_text(doc.rstrip() + DOC_NOTE, encoding="utf-8")
    print("Full Daily Ledger disable block inserted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
