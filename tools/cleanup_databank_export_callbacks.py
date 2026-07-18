#!/usr/bin/env python3
"""Safely remove legacy Data Bank export callbacks from the SPINA source.

This tool is intentionally conservative. It removes the old callback function
bodies only when their names have no remaining *real* references outside the
function bodies themselves.

Older UI-cleanup passes may leave harmless string references inside generated
hide/destroy blocks near the bottom of the app source. Those references are not
call sites, so this tool reports and ignores them only when the surrounding
context clearly belongs to a generated cleanup/hide block.
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

STALE_CLEANUP_CONTEXT_MARKERS = (
    "from transactions, full ledger, export template, and import excel",
    "exports, date range template, jsonl month, and daily excel template",
    "legacy clients-tab action",
    "legacy clients tab action",
    "data bank export",
    "databank export",
    "_spina_databank_export",
    "databank_exports_removed",
    "_spina_parent_has_databank_export_buttons",
    "_spina_original_app_init_for_databank_exports",
    "_spina_remove_databank",
    "visible data bank export widgets",
    "hide-only",
    "hide/destroy",
    "destroy",
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


def _looks_like_string_reference(line: str, function_name: str) -> bool:
    stripped = line.strip()
    quoted = f'"{function_name}"' in stripped or f"'{function_name}'" in stripped
    if quoted:
        return True
    # Generated cleanup dictionaries/tuples sometimes store strings with commas
    # or colons after indentation; those are not function calls.
    return (
        function_name in stripped
        and "(" not in stripped.split(function_name, 1)[1][:3]
        and any(token in stripped for token in ('"', "'", ":", ","))
    )


def _is_stale_cleanup_reference(lines: list[str], index: int, function_name: str) -> bool:
    """Return True only for harmless generated cleanup/hide-block references."""
    if not _looks_like_string_reference(lines[index], function_name):
        return False

    start = max(0, index - 90)
    end = min(len(lines), index + 91)
    context = "\n".join(lines[start:end]).lower()
    return any(marker in context for marker in STALE_CLEANUP_CONTEXT_MARKERS)


def _external_references(
    lines: list[str],
    function_name: str,
    own_ranges: list[tuple[int, int, int]],
) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    pattern = re.compile(rf"\b{re.escape(function_name)}\b")
    real_refs: list[tuple[int, str]] = []
    ignored_stale_refs: list[tuple[int, str]] = []

    for idx, line in enumerate(lines):
        if not pattern.search(line):
            continue
        if _inside_any(idx, own_ranges):
            continue
        if _is_stale_cleanup_reference(lines, idx, function_name):
            ignored_stale_refs.append((idx + 1, line.rstrip("\n")))
            continue
        real_refs.append((idx + 1, line.rstrip("\n")))

    return real_refs, ignored_stale_refs


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
    ignored_refs: dict[str, list[tuple[int, str]]] = {}

    for function_name in TARGET_FUNCTIONS:
        ranges = _find_function_ranges(lines, function_name)
        refs, stale_refs = _external_references(lines, function_name, ranges)
        print(
            f"[SPINA] {function_name}: definitions={len(ranges)} "
            f"external_references={len(refs)} ignored_stale_cleanup_references={len(stale_refs)}",
            flush=True,
        )
        if stale_refs:
            ignored_refs[function_name] = stale_refs
        if refs:
            unsafe_refs[function_name] = refs
        for start, end, indent in ranges:
            all_ranges.append((start, end, indent, function_name))

    if ignored_refs:
        print("[SPINA] Ignored stale cleanup-block references:", flush=True)
        for function_name, refs in ignored_refs.items():
            print(f"[SPINA] Stale references for {function_name}:", flush=True)
            for line_no, text in refs[:25]:
                print(f"  line {line_no}: {text}", flush=True)
            if len(refs) > 25:
                print(f"  ... {len(refs) - 25} more", flush=True)

    if unsafe_refs:
        print("[SPINA][STOP] Remaining real references found. No callbacks were removed.", flush=True)
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
