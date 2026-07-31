#!/usr/bin/env python3
"""Remove startup blocks made redundant by Wave 89."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MAIN_REMOVED_MARKER = "# --- Legacy desktop main implementation removed Wave 90 ---"
PLACEHOLDER_REMOVED_MARKER = "# --- Placeholder entry point removed Wave 90 ---"


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def is_main_guard(node: ast.If) -> bool:
    test = node.test
    return (
        isinstance(test, ast.Compare)
        and isinstance(test.left, ast.Name)
        and test.left.id == "__name__"
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.Eq)
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value == "__main__"
    )


def line_offsets(text: str) -> list[int]:
    offsets = [0]
    for line in text.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    return offsets


def node_span(node: ast.AST, offsets: list[int], text: str) -> tuple[int, int]:
    start = offsets[node.lineno - 1] + node.col_offset
    end = offsets[node.end_lineno - 1] + node.end_col_offset
    while end < len(text) and text[end] in "\r\n":
        end += 1
    return start, end


def main() -> None:
    original = DESKTOP.read_text(encoding="utf-8")
    tree = ast.parse(original, filename=str(DESKTOP))
    offsets = line_offsets(original)

    legacy_main = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    ]
    placeholders = [
        node for node in tree.body
        if isinstance(node, ast.If)
        and is_main_guard(node)
        and len(node.body) == 1
        and isinstance(node.body[0], ast.Pass)
    ]
    final_calls = [
        node for node in tree.body
        if isinstance(node, ast.If)
        and is_main_guard(node)
        and any(
            isinstance(call, ast.Call) and dotted(call.func) == "main"
            for call in ast.walk(node)
        )
    ]

    if not legacy_main and not placeholders:
        assert original.count(MAIN_REMOVED_MARKER) == 1
        assert original.count(PLACEHOLDER_REMOVED_MARKER) == 2
        assert len(final_calls) == 1
        print("Wave 90 startup cleanup already applied.")
        return

    assert len(legacy_main) == 1, len(legacy_main)
    assert len(placeholders) == 2, [node.lineno for node in placeholders]
    assert len(final_calls) == 1, [node.lineno for node in final_calls]

    replacements: list[tuple[int, int, str]] = [
        (*node_span(legacy_main[0], offsets, original), MAIN_REMOVED_MARKER + "\n\n")
    ]
    for placeholder in placeholders:
        replacements.append(
            (*node_span(placeholder, offsets, original), PLACEHOLDER_REMOVED_MARKER + "\n\n")
        )

    cleaned = original
    for start, end, replacement in sorted(replacements, reverse=True):
        cleaned = cleaned[:start] + replacement + cleaned[end:]

    cleaned = cleaned.rstrip() + "\n"
    cleaned_tree = ast.parse(cleaned, filename=str(DESKTOP))
    assert not [
        node for node in cleaned_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    ]
    assert not [
        node for node in cleaned_tree.body
        if isinstance(node, ast.If)
        and is_main_guard(node)
        and len(node.body) == 1
        and isinstance(node.body[0], ast.Pass)
    ]
    cleaned_final_calls = [
        node for node in cleaned_tree.body
        if isinstance(node, ast.If)
        and is_main_guard(node)
        and any(
            isinstance(call, ast.Call) and dotted(call.func) == "main"
            for call in ast.walk(node)
        )
    ]
    assert len(cleaned_final_calls) == 1
    assert cleaned.count(MAIN_REMOVED_MARKER) == 1
    assert cleaned.count(PLACEHOLDER_REMOVED_MARKER) == 2

    DESKTOP.write_text(cleaned, encoding="utf-8")
    print("Wave 90 startup cleanup applied.")


if __name__ == "__main__":
    main()
