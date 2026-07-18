#!/usr/bin/env python3
"""Remove confirmed legacy Data Bank export UI lines from the SPINA source.

This is intentionally narrower than deleting export functions. It only removes the
visible Data Bank export strip/button creation lines that were confirmed by the
UI/action inventory. The old callbacks stay in the file until they are proven
unused and safe to delete.
"""

from __future__ import annotations

from pathlib import Path

APP_FILE = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
DOC_FILE = Path("docs/code-issue-review.md")

# Runtime-injected blocks from earlier hide-only tools. Remove them during source
# cleanup so the local app file becomes cleaner instead of accumulating patches.
OLD_BLOCKS = (
    (
        "# --- BEGIN: SPINA REMOVE DATABANK EXPORT CONTROLS ---",
        "# --- END: SPINA REMOVE DATABANK EXPORT CONTROLS ---",
    ),
)

LABEL_TERMS = (
    "exports",
    "date range template",
    "jsonl month",
    "export jsonl (month)",
    "daily excel template",
    "daily collection excel template",
    "create daily collection excel template",
)

UI_TERMS = (
    "ttk.label",
    "tk.label",
    "ctklabel",
    ".label(",
    "ttk.button",
    "tk.button",
    "ctkbutton",
    ".button(",
    "command=",
)

SAFE_CONTEXT_TERMS = (
    "right_actions",
    "row2",
    "databank",
    "data bank",
    "export_jsonl_month",
    "export_daily_collection_template",
)

DOC_NOTE = """

## Phase 6 Data Bank export UI source cleanup

The confirmed legacy Data Bank export UI creation lines were removed from the
local source by `tools/cleanup_databank_export_ui_source.py`.

This source cleanup is intentionally narrow:

- removes visible Data Bank export label/button creation lines only
- removes earlier runtime hide-only Data Bank export patch blocks if present
- keeps `export_jsonl_month` and `export_daily_collection_template` functions for now
- does not change notes, collector route, client statements, balances, 7x7,
  interest, payment allocation, report math, or database writes
"""


def remove_old_blocks(text: str) -> tuple[str, int]:
    removed = 0
    for start_marker, end_marker in OLD_BLOCKS:
        while True:
            start = text.find(start_marker)
            if start == -1:
                break
            end = text.find(end_marker, start)
            if end == -1:
                raise SystemExit(f"Found block start without end marker: {start_marker}")
            end += len(end_marker)
            text = text[:start].rstrip() + "\n\n" + text[end:].lstrip()
            removed += 1
    return text, removed


def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def is_confirmed_databank_export_ui_line(line: str) -> bool:
    lowered = line.lower()
    if not _has_any(lowered, LABEL_TERMS):
        return False
    if not _has_any(lowered, UI_TERMS):
        return False

    # Do not remove function definitions or non-UI text. The confirmed inventory
    # hits were button/label creation lines in Data Bank action rows.
    stripped = lowered.strip()
    if stripped.startswith("def ") or stripped.startswith("class "):
        return False
    if stripped.startswith("#"):
        return False

    # Keep this narrow to avoid deleting report/client/collector UI that happens
    # to contain words like exportselection=False.
    return _has_any(lowered, SAFE_CONTEXT_TERMS) or "text=" in lowered


def cleanup_source_lines(source: str) -> tuple[str, int]:
    cleaned: list[str] = []
    removed = 0
    for line in source.splitlines():
        if is_confirmed_databank_export_ui_line(line):
            indent = line[: len(line) - len(line.lstrip())]
            cleaned.append(indent + "# SPINA removed legacy Data Bank export UI control")
            removed += 1
        else:
            cleaned.append(line)
    suffix = "\n" if source.endswith("\n") else ""
    return "\n".join(cleaned) + suffix, removed


def main() -> int:
    print("[SPINA] Data Bank export UI source cleanup starting...", flush=True)
    if not APP_FILE.exists():
        raise SystemExit(f"App file not found: {APP_FILE}")

    source = APP_FILE.read_text(encoding="utf-8")
    source, old_blocks_removed = remove_old_blocks(source)
    source, ui_lines_removed = cleanup_source_lines(source)
    APP_FILE.write_text(source, encoding="utf-8")

    if DOC_FILE.exists():
        doc = DOC_FILE.read_text(encoding="utf-8")
        if "## Phase 6 Data Bank export UI source cleanup" not in doc:
            DOC_FILE.write_text(doc.rstrip() + DOC_NOTE, encoding="utf-8")

    print(f"[SPINA] Old Data Bank runtime blocks removed: {old_blocks_removed}", flush=True)
    print(f"[SPINA] Data Bank export UI lines removed: {ui_lines_removed}", flush=True)
    print("[SPINA] Done. Run py_compile and open Data Bank to verify.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
