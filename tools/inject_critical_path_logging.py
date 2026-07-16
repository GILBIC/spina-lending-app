#!/usr/bin/env python3
"""Inject critical-path exception logging wrappers into the SPINA source.

This tool is intentionally narrow and behavior-preserving: it wraps selected
functions and App methods so unhandled exceptions are logged before being
re-raised. It does not change loan, balance, payment, report math, or database
write behavior.
"""

from __future__ import annotations

from pathlib import Path

APP_FILE = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
DOC_FILE = Path("docs/code-issue-review.md")
START = "# --- BEGIN: SPINA CRITICAL-PATH EXCEPTION LOGGING ---"
END = "# --- END: SPINA CRITICAL-PATH EXCEPTION LOGGING ---"

BLOCK = r'''
# --- BEGIN: SPINA CRITICAL-PATH EXCEPTION LOGGING ---
# Logs unhandled exceptions on critical paths before re-raising them.
# This is diagnostic only: normal successful behavior is unchanged.
def _spina_critical_log(context, exc):
    try:
        if "_log_exc" in globals():
            _log_exc(str(context), exc)
        elif "_spina_early_log" in globals():
            _spina_early_log(str(context), exc)
        else:
            print("[SPINA][CRITICAL] %s: %s" % (context, exc), flush=True)
    except Exception:
        try:
            print("[SPINA][CRITICAL] %s: %s" % (context, exc), flush=True)
        except Exception:
            pass


def _spina_wrap_critical_callable(owner, attr_name, label):
    try:
        original = getattr(owner, attr_name, None)
        if not callable(original):
            return False
        if getattr(original, "_spina_critical_wrapped", False):
            return True

        def _spina_critical_wrapped(*args, **kwargs):
            try:
                return original(*args, **kwargs)
            except Exception as _spina_critical_exc:
                _spina_critical_log(label, _spina_critical_exc)
                raise

        _spina_critical_wrapped.__name__ = getattr(original, "__name__", attr_name)
        _spina_critical_wrapped.__doc__ = getattr(original, "__doc__", None)
        _spina_critical_wrapped._spina_critical_wrapped = True
        setattr(owner, attr_name, _spina_critical_wrapped)
        return True
    except Exception as _spina_wrap_exc:
        _spina_critical_log("critical wrapper setup: " + str(label), _spina_wrap_exc)
        return False


def _spina_wrap_critical_global(name):
    try:
        original = globals().get(name)
        if not callable(original):
            return False
        if getattr(original, "_spina_critical_wrapped", False):
            return True

        def _spina_critical_wrapped(*args, **kwargs):
            try:
                return original(*args, **kwargs)
            except Exception as _spina_critical_exc:
                _spina_critical_log("global " + str(name), _spina_critical_exc)
                raise

        _spina_critical_wrapped.__name__ = getattr(original, "__name__", name)
        _spina_critical_wrapped.__doc__ = getattr(original, "__doc__", None)
        _spina_critical_wrapped._spina_critical_wrapped = True
        globals()[name] = _spina_critical_wrapped
        return True
    except Exception as _spina_wrap_exc:
        _spina_critical_log("critical global wrapper setup: " + str(name), _spina_wrap_exc)
        return False


for _spina_critical_global in (
    "_spina_pg_connect_db",
    "connect_db",
    "generate_client_pdf",
    "print_full_daily_ledger",
    "import_from_excel_with_reasons",
    "_app_import_clients_from_excel",
    "_spina_record_report_generation",
):
    _spina_wrap_critical_global(_spina_critical_global)

try:
    _SPINA_CRITICAL_APP_METHODS = (
        "_verify_login",
        "_prompt_login",
        "backup_postgres_database",
        "_create_postgres_backup_file",
        "_restore_backup_to_test_database",
        "generate_pdf_selected",
        "_import_from_excel_entry_worker",
        "_import_from_excel_core",
        "import_from_excel",
        "import_clients_from_excel",
        "restore_selected",
    )
    for _spina_critical_method in _SPINA_CRITICAL_APP_METHODS:
        _spina_wrap_critical_callable(App, _spina_critical_method, "App." + str(_spina_critical_method))
except Exception as _spina_critical_setup_exc:
    _spina_critical_log("critical App wrapper setup", _spina_critical_setup_exc)
# --- END: SPINA CRITICAL-PATH EXCEPTION LOGGING ---
'''.strip()

DOC_NOTE = """

## Phase 4 critical-path runtime logging

SPINA now wraps selected critical paths so unhandled exceptions are logged before they are re-raised. This makes failures easier to diagnose without changing successful behavior.

Covered paths include startup/database connection, login prompts, backup/restore helpers, report/PDF generation, and Excel import entry points.

Safety rules for this phase:

- no loan, balance, payment, or report math was changed
- successful behavior is unchanged
- wrappers only add logging when an exception escapes a covered function
- internal exceptions intentionally swallowed by older code are not changed in this PR
"""


def remove_existing_block(text: str) -> str:
    start = text.find(START)
    if start == -1:
        return text
    end = text.find(END, start)
    if end == -1:
        raise SystemExit("Found critical logging block start without end marker")
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
        if "## Phase 4 critical-path runtime logging" not in doc:
            DOC_FILE.write_text(doc.rstrip() + DOC_NOTE, encoding="utf-8")
    print("Critical-path exception logging block inserted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
