#!/usr/bin/env python3
"""Plan/apply a narrow cleanup for modern UI pass-only exception handlers.

This tool intentionally targets only the modern UI chrome/sidebar/theme lines
approved by the preceding planner. Default mode is dry-run; use --apply only
after reviewing the JSON output.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

APP_FILE = "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"

# These are the 19 selected targets from tools/plan_modern_ui_pass_only_cleanup.py.
# The list is deliberately line-specific so the tool fails closed if the app moves.
TARGETS = [
    {"line": 14971, "scope": "App.set_theme", "key": "modern_ui_pass_14971", "message": "modern UI header theme refresh skipped"},
    {"line": 14982, "scope": "App.set_theme", "key": "modern_ui_pass_14982", "message": "modern UI shell theme refresh skipped"},
    {"line": 15887, "scope": "App._select_side_tab", "key": "modern_ui_pass_15887", "message": "modern UI sidebar select logging fallback skipped"},
    {"line": 15891, "scope": "App._select_side_tab", "key": "modern_ui_pass_15891", "message": "modern UI sidebar selection refresh skipped"},
    {"line": 15902, "scope": "App._rebuild_side_nav", "key": "modern_ui_pass_15902", "message": "modern UI sidebar child cleanup skipped"},
    {"line": 15913, "scope": "App._rebuild_side_nav", "key": "modern_ui_pass_15913", "message": "modern UI sidebar frame layout skipped"},
    {"line": 15946, "scope": "App._rebuild_side_nav", "key": "modern_ui_pass_15946", "message": "modern UI sidebar subtitle build skipped"},
    {"line": 15970, "scope": "App._rebuild_side_nav", "key": "modern_ui_pass_15970", "message": "modern UI sidebar button logging fallback skipped"},
    {"line": 15990, "scope": "App._rebuild_side_nav", "key": "modern_ui_pass_15990", "message": "modern UI sidebar user label build skipped"},
    {"line": 16026, "scope": "App._refresh_side_nav_selection", "key": "modern_ui_pass_16026", "message": "modern UI sidebar button selection style skipped"},
    {"line": 16039, "scope": "App._refresh_modern_shell_theme", "key": "modern_ui_pass_16039", "message": "modern UI shell style refresh skipped"},
    {"line": 16046, "scope": "App._refresh_modern_shell_theme", "key": "modern_ui_pass_16046", "message": "modern UI shell sidebar selection fallback skipped"},
    {"line": 16103, "scope": "App._tk_button_hover", "key": "modern_ui_pass_16103", "message": "modern UI button hover binding skipped"},
    {"line": 16147, "scope": "App._set_mode", "key": "modern_ui_pass_16147", "message": "modern UI mode toggle refresh skipped"},
    {"line": 16176, "scope": "App._refresh_mode_toggle", "key": "modern_ui_pass_16176", "message": "modern UI mode button style skipped"},
    {"line": 16185, "scope": "App._refresh_mode_toggle", "key": "modern_ui_pass_16185", "message": "modern UI mode status label refresh skipped"},
    {"line": 16194, "scope": "App._refresh_header_theme", "key": "modern_ui_pass_16194", "message": "modern UI header background refresh skipped"},
    {"line": 16201, "scope": "App._refresh_header_theme", "key": "modern_ui_pass_16201", "message": "modern UI header frame color refresh skipped"},
    {"line": 16208, "scope": "App._refresh_header_theme", "key": "modern_ui_pass_16208", "message": "modern UI header title color refresh skipped"},
]

PROTECTED_WORDS = (
    "payment", "report", "pdf", "balance", "7x7", "7×7", "collector", "route",
    "ledger", "renew", "transaction", "principal", "interest", "backup", "restore",
    "database", "migration", "postgres", "pg_", "cash control", "payroll", "receipt",
)


def context(lines: list[str], line_no: int, radius: int = 6) -> list[dict[str, Any]]:
    start = max(1, line_no - radius)
    end = min(len(lines), line_no + radius)
    return [{"line": i, "text": lines[i - 1].rstrip("\n")} for i in range(start, end + 1)]


def has_protected_context(lines: list[str], line_no: int, radius: int = 4) -> bool:
    blob = "\n".join(x["text"].lower() for x in context(lines, line_no, radius))
    return any(word in blob for word in PROTECTED_WORDS)


def inspect_target(lines: list[str], target: dict[str, Any]) -> dict[str, Any]:
    line_no = int(target["line"])
    key = str(target["key"])
    already_clean = key in "\n".join(lines)
    item: dict[str, Any] = {
        "line": line_no,
        "scope": target["scope"],
        "key": key,
        "already_clean": already_clean,
        "safe": False,
        "reason": "not inspected",
        "context": context(lines, line_no),
    }

    if already_clean:
        item["safe"] = True
        item["reason"] = "already contains cleanup log key"
        return item

    if line_no < 1 or line_no + 1 > len(lines):
        item["reason"] = "line outside file"
        return item

    exc_line = lines[line_no - 1]
    pass_line = lines[line_no]
    if exc_line.strip() != "except Exception:":
        item["reason"] = "target line is not exact except Exception"
        return item
    if pass_line.strip() != "pass":
        item["reason"] = "target handler is not exact pass-only body"
        return item
    if has_protected_context(lines, line_no):
        item["reason"] = "protected word found near target"
        return item
    if "_log_suppressed_once" not in "\n".join(lines[:2000]):
        item["reason"] = "_log_suppressed_once helper not found near app helpers"
        return item

    item["safe"] = True
    item["reason"] = "exact modern UI pass-only handler match"
    return item


def replacement_for(lines: list[str], target: dict[str, Any]) -> list[str]:
    line_no = int(target["line"])
    exc_line = lines[line_no - 1]
    pass_line = lines[line_no]
    exc_indent = exc_line[: len(exc_line) - len(exc_line.lstrip())]
    body_indent = pass_line[: len(pass_line) - len(pass_line.lstrip())]
    key = str(target["key"])
    msg = str(target["message"])
    return [
        f"{exc_indent}except Exception as __spina_exc:\n",
        f"{body_indent}_log_suppressed_once('{key}', '{msg}', __spina_exc)\n",
        f"{body_indent}pass\n",
    ]


def build_report(path: Path, *, apply: bool) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    sites = [inspect_target(lines, target) for target in TARGETS]
    safe_sites = [s for s in sites if s["safe"] and not s["already_clean"]]
    already_clean_count = sum(1 for s in sites if s["already_clean"])
    unsafe_sites = [s for s in sites if not s["safe"]]
    safe = (not unsafe_sites) and (len(safe_sites) + already_clean_count == len(TARGETS))

    report: dict[str, Any] = {
        "file": str(path),
        "apply": apply,
        "target_count": len(TARGETS),
        "safe_candidate_count": len(safe_sites),
        "already_clean_count": already_clean_count,
        "unsafe_count": len(unsafe_sites),
        "safe": safe,
        "patched": False,
        "app_source_modified": False,
        "selected_scope": "modern UI chrome/sidebar/theme only",
        "sites": sites,
        "recommendations": [
            "Review this dry-run JSON before applying.",
            "This tool targets only the 19 modern UI chrome/sidebar/theme pass-only handlers from the approved plan.",
            "Run with --apply only if safe is true and unsafe_count is 0.",
            "After apply, rerun pass-only and modern UI cleanup plan audits.",
            "Smoke-test theme toggle, sidebar navigation, and Regular/7x7 mode switch after apply.",
        ],
    }

    if apply and safe and safe_sites:
        patched_lines = list(lines)
        targets_by_line = {int(t["line"]): t for t in TARGETS}
        # Patch from bottom to top so original line numbers stay valid.
        for line_no in sorted((int(s["line"]) for s in safe_sites), reverse=True):
            target = targets_by_line[line_no]
            repl = replacement_for(patched_lines, target)
            patched_lines[line_no - 1 : line_no + 1] = repl
        path.write_text("".join(patched_lines), encoding="utf-8")
        report["patched"] = True
        report["app_source_modified"] = True
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan/apply modern UI pass-only cleanup")
    parser.add_argument("file", nargs="?", default=APP_FILE)
    parser.add_argument("--apply", action="store_true", help="modify the app file after safety checks")
    parser.add_argument("--json", dest="json_path", default=None, help="write report JSON to this path")
    args = parser.parse_args()

    path = Path(args.file)
    report = build_report(path, apply=bool(args.apply))
    out = json.dumps(report, indent=2, ensure_ascii=False)
    if args.json_path:
        Path(args.json_path).write_text(out + "\n", encoding="utf-8")
    print(out)
    return 0 if report["safe"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
