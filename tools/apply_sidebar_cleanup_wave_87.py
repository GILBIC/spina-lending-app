#!/usr/bin/env python3
"""Remove sidebar wrappers made redundant by Wave 86."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"

BLOCKS = (
    (
        "# --- BEGIN: Modern sidebar nav refresh after role changes ---",
        "# --- END: Modern sidebar nav refresh after role changes ---",
        "# --- Legacy modern sidebar role wrapper removed Wave 87 ---",
    ),
    (
        "# --- BEGIN: v13 side-tabs-only UI fix ---",
        "# --- END: v13 side-tabs-only UI fix ---",
        "# --- Legacy v13 sidebar wrapper removed Wave 87 ---",
    ),
)


def replace_marked_block(source: str, begin: str, end: str, replacement: str) -> str:
    if begin not in source:
        if replacement in source and end not in source:
            return source
        raise AssertionError(f"Missing sidebar cleanup marker: {begin}")
    assert source.count(begin) == 1, (begin, source.count(begin))
    assert source.count(end) == 1, (end, source.count(end))
    start = source.index(begin)
    finish = source.index(end, start) + len(end)
    while finish < len(source) and source[finish] in "\r\n":
        finish += 1
    return source[:start] + replacement + "\n\n" + source[finish:]


def main() -> None:
    original = DESKTOP.read_text(encoding="utf-8")
    cleaned = original
    for begin, end, replacement in BLOCKS:
        cleaned = replace_marked_block(cleaned, begin, end, replacement)

    ast.parse(cleaned, filename=str(DESKTOP))
    normalized = cleaned.rstrip() + "\n"
    if normalized == original:
        print("Wave 87 sidebar cleanup already applied.")
        return

    DESKTOP.write_text(normalized, encoding="utf-8")
    print("Wave 87 sidebar cleanup applied.")


if __name__ == "__main__":
    main()
