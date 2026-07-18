#!/usr/bin/env python3
"""Safely remove legacy Data Bank export callbacks from the SPINA source.

This tool is intentionally conservative. It removes the old callback function
bodies only when their names have no remaining references outside the function
bodies themselves. If any reference remains, it stops and prints the lines for
manual review.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

APP_FILE = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
TARGET_FUNCTIONS = (
    "export_jsonl_month",
    "export_daily_collection_template",
)


def _line_indent(line: str) -> int:
    return len(line) - len(line.lstrip(" \t"))


def _is_decorator(line: str) -> bool:
    return line.lstrip().startswith("@")


def _find_function_ranges(lines: list[str], function_name: str) -> list[tuple[int, int, int]]:
    """Return 0-based inclusive/exclusive ranges for a function definition.

    Each result is (start_index, end_index, indent).
    """
    pattern = re.compile(rf"^(?P<indent>[ \t]*)def\s+{re.escape(function_name)}\s*\(")
    ranges: list[tuple[int, int, int]] = []

    i = 0
    while i < len(lines):
        match = pattern.match(lines[i])
        if not match:
            i += 1
            continue

        def_start = i
        # Include immediately preceding decorators at the same indentation level.
        j = i - 1
        while j >= 0 and _is_decorator(lines[j]) and _line_indent(lines[j]) == _line_indent(lines[i]):
            def_start = j
            j -= 1

        indent = len(match.group("indent"))
        end = i + 1
        while end < len(lines):
            stripped = lines[end].strip()
            if not stripped:
                end += 1
                continue
            current_indent = _line_indent(lines[end])
            if current_indent <= indent and not _is_decorator(lines[end]):
                break
            end += 1

        ranges.append((def_start, end, indent))
        i = end

    return ranges


def _inside_any(index: int, ranges: list[tuple[int, int, int]]) -> bool:
    return any(start <= index < end for start, end, _indent in ranges)


def _external_references(lines: list[str], function_name: str, own_ranges: list[tuple[int, int, int]]) -> list[tuple[int, str]]:
    pattern = re.compile(rf"\b{re.escape(function_name)}\b")
    refs: list[tuple[int, str]] = []
    for idx, line in enumerate(lines):
        if not pattern.search(line):
            continue
        if _inside_any(idx, own_ranges):
            continue
        refs.append((idx + 1, line.rstrip("\n")))
    return refs


def _remove_ranges(lines: list[str], ranges: list[tuple[int, int, int]]) -> list[str]:
    if not ranges:
        return lines
    remove_flags = [False] * len(lines)
    for start, end, _indent in ranges:
        for i in range(start, end):
            remove_flags[i] = True
    return [line for i, line in enumerate(lines) if not remove_flags[i]]


def main() -> int:
    print("[SPINA] Data Bank export callback cleanup starting...", flush=True)

    if not APP_FILE.exists():
        print(f"[SPINA][ERROR] Missing app file: {APP_FILE}", flush=True)
        return 2

    source = APP_FILE.read_text(encoding="utf-8")
    lines = source.splitlines(keepends=True)

    all_ranges: list[tuple[int, int, int, str]] = []
    unsafe_refs: dict[str, list[tuple[int, str]]] = {}

    for function_name in TARGET_FUNCTIONS:
        ranges = _find_function_ranges(lines, function_name)
        refs = _external_references(lines, function_name, ranges)
        print(
            f"[SPINA] {function_name}: definitions={len(ranges)} external_references={len(refs)}",
            flush=True,
        )
        if refs:
            unsafe_refs[function_name] = refs
        for start, end, indent in ranges:
            all_ranges.append((start, end, indent, function_name))

    if unsafe_refs:
        print("[SPINA][STOP] Remaining references found. No callbacks were removed.", flush=True)
        for function_name, refs in unsafe_refs.items():
            print(f"[SPINA] References for {function_name}:", flush=True)
            for line_no, text in refs[:25]:
                print(f"  line {line_no}: {text}", flush=True)
            if len(refs) > 25:
                print(f"  ... {len(refs) - 25} more", flush=True)
        return 1

    if not all_ranges:
        print("[SPINA] No target callback definitions found. Nothing to remove.", flush=True)
        return 0

    # Remove from bottom to top by using flag array against 3-tuple ranges.
    compact_ranges = [(start, end, indent) for start, end, indent, _name in all_ranges]
    new_lines = _remove_ranges(lines, compact_ranges)
    removed_lines = len(lines) - len(new_lines)

    APP_FILE.write_text("".join(new_lines), encoding="utf-8")
    print(f"[SPINA] Removed callback definitions: {len(all_ranges)}", flush=True)
    print(f"[SPINA] Removed source lines: {removed_lines}", flush=True)
    print("[SPINA] Done. Run py_compile and test Data Bank.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
