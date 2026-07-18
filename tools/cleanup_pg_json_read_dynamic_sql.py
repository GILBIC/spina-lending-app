#!/usr/bin/env python3
"""Plan/apply a safe cleanup for the PG JSON read dynamic SQL site.

This tool is intentionally narrow. It only targets the one non-protected
site reported by tools/audit_dynamic_sql_context.py:

    cur.execute(f'SELECT value FROM {table} WHERE key=%s', (key,))

The existing helper _spina_pg_json_table_for_path currently returns only two
literal table names. This cleanup replaces the f-string SQL with explicit
fixed-table branches, matching the existing write-json logic.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_APP_FILE = "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"

NEEDLE = "                cur.execute(f'SELECT value FROM {table} WHERE key=%s', (key,))"
REPLACEMENT_LINES = [
    "                if table == 'app_settings_store':",
    "                    cur.execute('SELECT value FROM app_settings_store WHERE key=%s', (key,))",
    "                elif table == 'app_json_store':",
    "                    cur.execute('SELECT value FROM app_json_store WHERE key=%s', (key,))",
    "                else:",
    "                    raise ValueError(f'Unexpected PostgreSQL JSON storage table: {table!r}')",
]
REPLACEMENT = "\n".join(REPLACEMENT_LINES)

ALREADY_CLEAN_MARKERS = [
    "SELECT value FROM app_settings_store WHERE key=%s",
    "SELECT value FROM app_json_store WHERE key=%s",
    "Unexpected PostgreSQL JSON storage table",
]


def _line_number(text: str, needle: str) -> int | None:
    for idx, line in enumerate(text.splitlines(), start=1):
        if line == needle:
            return idx
    return None


def _slice_context(lines: list[str], line_no: int | None, radius: int = 8) -> list[dict[str, Any]]:
    if not line_no:
        return []
    start = max(1, line_no - radius)
    end = min(len(lines), line_no + radius)
    return [{"line": i, "text": lines[i - 1]} for i in range(start, end + 1)]


def _function_block(text: str, name: str) -> str:
    marker = f"def {name}("
    start = text.find(marker)
    if start < 0:
        return ""
    next_start = text.find("\ndef ", start + len(marker))
    if next_start < 0:
        return text[start:]
    return text[start:next_start]


def build_plan(path: Path, apply: bool = False) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    target_line = _line_number(text, NEEDLE)
    target_count = sum(1 for line in lines if line == NEEDLE)
    already_clean = all(marker in text for marker in ALREADY_CLEAN_MARKERS) and target_count == 0

    table_helper = _function_block(text, "_spina_pg_json_table_for_path")
    read_helper = _function_block(text, "_spina_pg_read_json")
    write_helper = _function_block(text, "_spina_pg_write_json")

    helper_returns_expected_tables = (
        "return 'app_settings_store'" in table_helper
        and "return 'app_json_store'" in table_helper
    )
    read_helper_has_expected_flow = (
        "table = _spina_pg_json_table_for_path(path)" in read_helper
        and NEEDLE.strip() in read_helper
    )
    write_helper_uses_fixed_tables = (
        "if table == 'app_settings_store':" in write_helper
        and "INSERT INTO app_settings_store" in write_helper
        and "INSERT INTO app_json_store" in write_helper
    )

    safe = (
        target_count == 1
        and helper_returns_expected_tables
        and read_helper_has_expected_flow
        and write_helper_uses_fixed_tables
    )

    reason = "safe fixed-table replacement candidate found"
    if already_clean:
        reason = "already clean; f-string dynamic SQL read is not present"
    elif target_count != 1:
        reason = f"expected exactly one target line, found {target_count}"
    elif not helper_returns_expected_tables:
        reason = "table helper does not show the expected fixed table-name returns"
    elif not read_helper_has_expected_flow:
        reason = "read helper does not match the expected flow"
    elif not write_helper_uses_fixed_tables:
        reason = "write helper does not show the expected fixed-table branch pattern"

    patched = False
    if apply and safe:
        new_text = text.replace(NEEDLE, REPLACEMENT, 1)
        path.write_text(new_text, encoding="utf-8")
        patched = True

    return {
        "file": str(path),
        "apply": apply,
        "line_count": len(lines),
        "candidate_count": 0 if already_clean else target_count,
        "safe": bool(safe),
        "already_clean": bool(already_clean),
        "patched": bool(patched),
        "reason": reason,
        "target_line": target_line,
        "helper_returns_expected_tables": bool(helper_returns_expected_tables),
        "read_helper_has_expected_flow": bool(read_helper_has_expected_flow),
        "write_helper_uses_fixed_tables": bool(write_helper_uses_fixed_tables),
        "original_context": _slice_context(lines, target_line),
        "replacement_preview": REPLACEMENT_LINES,
        "recommendations": [
            "Review this dry-run JSON before applying.",
            "This cleanup targets only the PostgreSQL JSON read helper f-string table identifier.",
            "Run with --apply only if safe is true and candidate_count is 1.",
            "After apply, run tools/audit_dynamic_sql_context.py again and upload the JSON report.",
            "Do not touch protected database/payment/report/collector/7x7/balance code from this tool.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app_file", nargs="?", default=DEFAULT_APP_FILE)
    parser.add_argument("--apply", action="store_true", help="Apply the narrow cleanup if it is safe.")
    parser.add_argument("--json", dest="json_path", help="Write the plan/report to this JSON file.")
    args = parser.parse_args()

    path = Path(args.app_file)
    if not path.exists():
        raise SystemExit(f"App file not found: {path}")

    report = build_plan(path, apply=args.apply)
    out = json.dumps(report, indent=2, ensure_ascii=False)
    if args.json_path:
        Path(args.json_path).write_text(out + "\n", encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
