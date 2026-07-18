#!/usr/bin/env python3
"""Inject Reports/PDF exception logging wrappers into the SPINA source.

This diagnostic tool is intentionally narrow and behavior-preserving. It wraps
selected Reports/PDF entry points so unhandled exceptions are logged before
being re-raised. It does not change loan, balance, 7x7, interest, payment
allocation, report math, or database write behavior.
"""

from __future__ import annotations

from pathlib import Path

APP_FILE = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
DOC_FILE = Path("docs/code-issue-review.md")
START = "# --- BEGIN: SPINA REPORTS/PDF EXCEPTION LOGGING ---"
END = "# --- END: SPINA REPORTS/PDF EXCEPTION LOGGING ---"

BLOCK = r'''
# --- BEGIN: SPINA REPORTS/PDF EXCEPTION LOGGING ---
# Logs unhandled exceptions on Reports/PDF paths before re-raising them.
# Diagnostic only: successful behavior and report calculations are unchanged.
def _spina_reports_pdf_log(context, exc):
    try:
        message = "reports/pdf: " + str(context)
        if "_log_exc" in globals():
            _log_exc(message, exc)
        elif "_log_suppressed_once" in globals():
            _log_suppressed_once("reports_pdf_" + str(context), message, exc)
        elif "_spina_early_log" in globals():
            _spina_early_log(message, exc)
        else:
            print("[SPINA][REPORTS_PDF] %s: %s" % (context, exc), flush=True)
    except Exception:
        try:
            print("[SPINA][REPORTS_PDF] %s: %s" % (context, exc), flush=True)
        except Exception:
            pass


def _spina_reports_pdf_wrap_callable(owner, attr_name, label):
    try:
        original = getattr(owner, attr_name, None)
        if not callable(original):
            return False
        if getattr(original, "_spina_reports_pdf_wrapped", False):
            return True

        def _spina_reports_pdf_wrapped(*args, **kwargs):
            try:
                return original(*args, **kwargs)
            except Exception as _spina_reports_pdf_exc:
                _spina_reports_pdf_log(label, _spina_reports_pdf_exc)
                raise

        _spina_reports_pdf_wrapped.__name__ = getattr(original, "__name__", attr_name)
        _spina_reports_pdf_wrapped.__doc__ = getattr(original, "__doc__", None)
        _spina_reports_pdf_wrapped._spina_reports_pdf_wrapped = True
        setattr(owner, attr_name, _spina_reports_pdf_wrapped)
        return True
    except Exception as _spina_reports_pdf_setup_exc:
        _spina_reports_pdf_log("wrapper setup: " + str(label), _spina_reports_pdf_setup_exc)
        return False


def _spina_reports_pdf_wrap_global(name):
    try:
        original = globals().get(name)
        if not callable(original):
            return False
        if getattr(original, "_spina_reports_pdf_wrapped", False):
            return True

        def _spina_reports_pdf_wrapped(*args, **kwargs):
            try:
                return original(*args, **kwargs)
            except Exception as _spina_reports_pdf_exc:
                _spina_reports_pdf_log("global " + str(name), _spina_reports_pdf_exc)
                raise

        _spina_reports_pdf_wrapped.__name__ = getattr(original, "__name__", name)
        _spina_reports_pdf_wrapped.__doc__ = getattr(original, "__doc__", None)
        _spina_reports_pdf_wrapped._spina_reports_pdf_wrapped = True
        globals()[name] = _spina_reports_pdf_wrapped
        return True
    except Exception as _spina_reports_pdf_setup_exc:
        _spina_reports_pdf_log("global wrapper setup: " + str(name), _spina_reports_pdf_setup_exc)
        return False


for _spina_reports_pdf_global in (
    "_get_reports_root",
    "_open_path",
    "_load_ledger_prefs",
    "_spina_record_report_generation",
    "_spina_save_closed_collector_route_copy",
    "generate_client_pdf",
    "print_full_daily_ledger",
    "print_collector_route_daily_ledger",
):
    _spina_reports_pdf_wrap_global(_spina_reports_pdf_global)

try:
    _SPINA_REPORTS_PDF_APP_METHODS = (
        "_build_reports_tab",
        "generate_pdf_selected",
        "print_client_statement",
        "print_statement",
        "print_full_daily_ledger",
        "print_collector_route_daily_ledger",
        "open_reports_folder",
        "open_reports_root",
    )
    for _spina_reports_pdf_method in _SPINA_REPORTS_PDF_APP_METHODS:
        _spina_reports_pdf_wrap_callable(App, _spina_reports_pdf_method, "App." + str(_spina_reports_pdf_method))
except Exception as _spina_reports_pdf_setup_exc:
    _spina_reports_pdf_log("App wrapper setup", _spina_reports_pdf_setup_exc)
# --- END: SPINA REPORTS/PDF EXCEPTION LOGGING ---
'''.strip()

DOC_NOTE = """

## Phase 5 Reports/PDF exception visibility

SPINA can now add narrow Reports/PDF exception wrappers for local diagnosis. The wrappers log unhandled exceptions before re-raising them, so failed PDF/report actions are easier to trace.

Covered paths include report root resolution, report folder opening, client statement PDF generation, full daily ledger printing, collector route ledger printing, and report-generation recording.

Safety rules for this phase:

- no loan, balance, 7x7, interest, payment allocation, or report math is changed
- successful behavior is unchanged
- wrappers only add logging when an exception escapes a covered Reports/PDF function
- internal exceptions intentionally swallowed by older code are not changed by this tool
"""


def remove_existing_block(text: str) -> str:
    start = text.find(START)
    if start == -1:
        return text
    end = text.find(END, start)
    if end == -1:
        raise SystemExit("Found reports/pdf logging block start without end marker")
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
        if "## Phase 5 Reports/PDF exception visibility" not in doc:
            DOC_FILE.write_text(doc.rstrip() + DOC_NOTE, encoding="utf-8")
    print("Reports/PDF exception logging block inserted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
