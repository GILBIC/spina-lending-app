#!/usr/bin/env python3
'''Remove account runtime definitions made redundant by Wave 83.'''
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
TEMPLATE_DIR = ROOT / "tools" / "wave84_templates"

BEGIN = "# --- BEGIN: v32 Modern Account-Based Login ---"
END = "# --- END: v32 Modern Account-Based Login ---"
REMOVE_APP_METHODS = {
    "_prompt_login",
    "_prompt_user_role",
    "_refresh_user_header",
    "switch_account",
}
TEST_TEMPLATES = {
    ROOT / "tools" / "test_login_dialog_presentation_wave_45.py":
        TEMPLATE_DIR / "test_login_dialog_presentation_wave_45.py.txt",
    ROOT / "tools" / "test_account_header_presentation_wave_46.py":
        TEMPLATE_DIR / "test_account_header_presentation_wave_46.py.txt",
    ROOT / "tools" / "test_account_permission_presentation_wave_47.py":
        TEMPLATE_DIR / "test_account_permission_presentation_wave_47.py.txt",
}

COMPACT_BLOCK = '''# --- BEGIN: v32 Modern Account-Based Login ---
# Wave 84: presentation dependencies enter through one Wave 46 configuration
# point; Wave 83 owns all final account runtime bindings.
from spina_app.theme_palettes import _spina_v32_login_colors
from spina_app.ui_controls import _spina_v32_login_button
from spina_app.account_header_presentation import (
    configure_account_header_dependencies as _wave46_configure_account_header_dependencies,
)

_spina_v32_orig_build_header = getattr(App, "_build_header", None)
_wave46_configure_account_header_dependencies(globals())
# --- END: v32 Modern Account-Based Login ---'''


def remove_app_methods(source: str) -> str:
    tree = ast.parse(source)
    app = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "App"
    )
    lines = source.splitlines(keepends=True)
    ranges: list[tuple[int, int]] = []
    for node in app.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name not in REMOVE_APP_METHODS:
            continue
        start = node.lineno - 1
        if node.decorator_list:
            start = min(start, *(item.lineno - 1 for item in node.decorator_list))
        ranges.append((start, node.end_lineno))

    for start, end in sorted(ranges, reverse=True):
        del lines[start:end]
    return "".join(lines)


def replace_runtime_block(source: str) -> str:
    start = source.find(BEGIN)
    if start < 0:
        raise AssertionError(f"Missing marker: {BEGIN}")
    end = source.find(END, start)
    if end < 0:
        raise AssertionError(f"Missing marker: {END}")
    end += len(END)
    return source[:start] + COMPACT_BLOCK + source[end:]


def write_if_changed(path: Path, content: str) -> bool:
    normalized = content.rstrip() + "\n"
    previous = path.read_text(encoding="utf-8") if path.exists() else None
    if previous == normalized:
        return False
    path.write_text(normalized, encoding="utf-8")
    return True


def main() -> None:
    original = DESKTOP.read_text(encoding="utf-8")
    cleaned = replace_runtime_block(remove_app_methods(original))
    ast.parse(cleaned)

    changed: list[str] = []
    if write_if_changed(DESKTOP, cleaned):
        changed.append(DESKTOP.relative_to(ROOT).as_posix())

    for destination, template in TEST_TEMPLATES.items():
        content = template.read_text(encoding="utf-8")
        if write_if_changed(destination, content):
            changed.append(destination.relative_to(ROOT).as_posix())

    print("Wave 84 cleanup applied." if changed else "Wave 84 cleanup already applied.")
    for path in changed:
        print(f"  changed: {path}")


if __name__ == "__main__":
    main()
