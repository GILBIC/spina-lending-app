#!/usr/bin/env python3
"""Insert an optional SPINA performance logging block.

The generated app block is disabled by default. Users enable it locally with:

    set SPINA_PERF_LOG=1

It wraps selected high-cost App methods after all patch layers are defined and
before main() is called, so it observes the final active implementations.

This tool modifies the local working copy only when it is run manually.
"""

from __future__ import annotations

from pathlib import Path

APP_FILE = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
DOC_FILE = Path("docs/code-issue-review.md")
START = "# --- BEGIN: SPINA OPTIONAL PERFORMANCE TIMING LOGS ---"
END = "# --- END: SPINA OPTIONAL PERFORMANCE TIMING LOGS ---"

BLOCK = r'''
# --- BEGIN: SPINA OPTIONAL PERFORMANCE TIMING LOGS ---
# Off by default. Enable locally with:
#   set SPINA_PERF_LOG=1
# Optional threshold in seconds:
#   set SPINA_PERF_THRESHOLD=0.25
# This is diagnostic only. It does not change loan, balance, report, or database logic.
def _spina_perf_logging_enabled():
    try:
        return str(os.environ.get("SPINA_PERF_LOG", "") or "").strip().lower() in {"1", "true", "yes", "on"}
    except Exception:
        return False


def _spina_perf_threshold_seconds():
    try:
        return max(0.0, float(os.environ.get("SPINA_PERF_THRESHOLD", "0.25") or 0.25))
    except Exception:
        return 0.25


def _spina_perf_log(message):
    # Use direct console output instead of SPINA's suppressed logger. This makes
    # performance diagnostics visible in the Command Prompt that launched SPINA.
    try:
        print(str(message), flush=True)
    except Exception:
        pass


def _spina_perf_wrap_app_method(method_name):
    try:
        original = getattr(App, method_name, None)
        if not callable(original):
            return False
        if getattr(original, "_spina_perf_wrapped", False):
            return True

        def _spina_perf_wrapped(self, *args, **kwargs):
            if not _spina_perf_logging_enabled():
                return original(self, *args, **kwargs)
            import time as _spina_perf_time
            started = _spina_perf_time.perf_counter()
            try:
                return original(self, *args, **kwargs)
            finally:
                elapsed = _spina_perf_time.perf_counter() - started
                if elapsed >= _spina_perf_threshold_seconds():
                    _spina_perf_log("[SPINA][PERF] App.%s took %.3fs" % (method_name, elapsed))

        _spina_perf_wrapped.__name__ = getattr(original, "__name__", method_name)
        _spina_perf_wrapped.__doc__ = getattr(original, "__doc__", None)
        _spina_perf_wrapped._spina_perf_wrapped = True
        setattr(App, method_name, _spina_perf_wrapped)
        return True
    except Exception as _spina_perf_error:
        try:
            _spina_early_log("perf_wrap_" + str(method_name), _spina_perf_error)
        except Exception:
            pass
        return False


for _spina_perf_method in (
    "refresh_clients",
    "refresh_collectors",
    "refresh_dashboard",
    "_populate_dashboard_tree",
    "refresh_data_grid",
    "_on_collectors_select",
    "_build_clients_tab",
    "_build_collectors_tab",
):
    _spina_perf_wrap_app_method(_spina_perf_method)
# --- END: SPINA OPTIONAL PERFORMANCE TIMING LOGS ---
'''.strip()

DOC_NOTE = """

## Phase 3 performance diagnostics

Optional timing logs can be enabled locally without changing normal app behavior:

```bat
python tools\\add_optional_performance_logs.py
set SPINA_PERF_LOG=1
set SPINA_PERF_THRESHOLD=0.25
python "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
```

When enabled, SPINA prints slow calls directly to the launching Command Prompt for selected high-cost screens such as Clients, Collector Route, Dashboard, and Data Bank refreshes. This helps identify the next one-screen performance target before changing loading or query behavior.
"""


def remove_existing_block(text: str) -> str:
    start = text.find(START)
    if start == -1:
        return text
    end = text.find(END, start)
    if end == -1:
        raise SystemExit("Found performance block start without end marker")
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
        if "## Phase 3 performance diagnostics" not in doc:
            DOC_FILE.write_text(doc.rstrip() + DOC_NOTE, encoding="utf-8")
    print("Optional performance timing block inserted. Set SPINA_PERF_LOG=1 to enable timing output.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
