#!/usr/bin/env python3
"""Remove shadowed duplicate App class methods from the SPINA source.

This script is intentionally narrow. It only removes earlier definitions of
selected methods inside the original App class body. Python keeps only the final
method with a repeated name during class creation, so earlier definitions are
shadowed and not callable after import.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

APP_FILE = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
DOC_FILE = Path("docs/code-issue-review.md")
TARGET_METHODS = {
    "_get_selected_report_client": 3,
    "_auto_load_report_note": 2,
}
MARKER = "## Phase 2 cleanup completed"


def _find_app_class(tree: ast.Module) -> ast.ClassDef:
    matches = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "App"]
    if len(matches) != 1:
        raise SystemExit(f"Expected exactly one App class, found {len(matches)}")
    return matches[0]


def _collect_methods(app_class: ast.ClassDef) -> dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]]:
    methods: dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]] = {}
    for node in app_class.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.setdefault(node.name, []).append(node)
    return methods


def _method_start_line(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    starts = [node.lineno]
    starts.extend(getattr(dec, "lineno", node.lineno) for dec in node.decorator_list)
    return min(starts)


def _remove_ranges(lines: list[str], ranges: list[tuple[int, int]]) -> list[str]:
    # Ranges are 1-based inclusive. Apply from bottom to top so earlier offsets stay valid.
    for start, end in sorted(ranges, reverse=True):
        del lines[start - 1:end]
    return lines


def _append_docs(removed: list[tuple[str, int, int]]) -> None:
    DOC_FILE.parent.mkdir(parents=True, exist_ok=True)
    text = DOC_FILE.read_text(encoding="utf-8") if DOC_FILE.exists() else "# SPINA code issue review\n"
    if MARKER in text:
        return
    lines = [
        "",
        "",
        MARKER,
        "",
        "Removed earlier duplicate `App` class method definitions that were shadowed inside the class body.",
        "Python binds only the final method with a repeated name when the class is created, so this cleanup keeps the active implementations and removes inactive earlier definitions.",
        "",
        "Removed definitions:",
    ]
    for name, start, end in removed:
        lines.append(f"- `App.{name}` earlier definition at lines {start}-{end}")
    lines.extend([
        "",
        "No monkey-patch chains, login/database logic, reports, collectors, dashboard, balances, or call sites were changed.",
    ])
    DOC_FILE.write_text(text.rstrip() + "\n" + "\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    source = APP_FILE.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(APP_FILE))
    app_class = _find_app_class(tree)
    methods = _collect_methods(app_class)

    remove_ranges: list[tuple[int, int]] = []
    removed: list[tuple[str, int, int]] = []

    for method_name, expected_count in TARGET_METHODS.items():
        group = methods.get(method_name, [])
        if len(group) != expected_count:
            raise SystemExit(
                f"Expected {expected_count} App.{method_name} definitions, found {len(group)}"
            )
        for node in group[:-1]:
            if node.decorator_list:
                raise SystemExit(f"Refusing to remove decorated method App.{method_name} at line {node.lineno}")
            start = _method_start_line(node)
            end = int(getattr(node, "end_lineno", node.lineno))
            remove_ranges.append((start, end))
            removed.append((method_name, start, end))

    if not remove_ranges:
        print("No duplicate App methods to remove.")
        return 0

    new_lines = _remove_ranges(source.splitlines(keepends=True), remove_ranges)
    APP_FILE.write_text("".join(new_lines), encoding="utf-8")

    # Re-parse and prove the targeted duplicate methods are gone.
    new_tree = ast.parse(APP_FILE.read_text(encoding="utf-8"), filename=str(APP_FILE))
    new_app = _find_app_class(new_tree)
    new_methods = _collect_methods(new_app)
    for method_name in TARGET_METHODS:
        count = len(new_methods.get(method_name, []))
        if count != 1:
            raise SystemExit(f"Expected one remaining App.{method_name}, found {count}")

    _append_docs(removed)

    subprocess.run([sys.executable, "-m", "py_compile", str(APP_FILE)], check=True)
    print("Removed shadowed App methods:")
    for method_name, start, end in removed:
        print(f"- App.{method_name}: lines {start}-{end}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
