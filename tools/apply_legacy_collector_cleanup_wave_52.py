from __future__ import annotations

import ast
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
UI_CONTROLS = ROOT / "spina_app" / "ui_controls.py"
DIAGNOSTIC = ROOT / "tools" / "wave52_diagnostic.txt"

LEGACY_BUILDER = "_spina_v25_build_collectors_tab"
LEGACY_BUTTON = "_spina_v25_collector_button"
ACTIVE_BUILDER = "_spina_v27_build_collectors_tab"
ACTIVE_ROUTE_BUTTON = "_spina_v27_route_button"
ACTIVE_LOGIN_BUTTON = "_spina_v32_login_button"


def line_offsets(text: str) -> list[int]:
    offsets = [0]
    for line in text.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    return offsets


def replacement_span(text: str, node: ast.AST, replacement: str = "") -> tuple[int, int, str]:
    offsets = line_offsets(text)
    start = offsets[node.lineno - 1]
    end = offsets[node.end_lineno]
    if not replacement:
        while end < len(text) and text[end] in "\r\n":
            end += 1
    return start, end, replacement


def apply_replacements(text: str, replacements: list[tuple[int, int, str]]) -> str:
    unique = {(start, end, replacement) for start, end, replacement in replacements}
    for start, end, replacement in sorted(unique, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text


def import_source(module: str, names: list[ast.alias]) -> str:
    if not names:
        return ""
    if len(names) == 1:
        alias = names[0]
        rendered = alias.name + (f" as {alias.asname}" if alias.asname else "")
        return f"from {module} import {rendered}\n"
    rows = [f"from {module} import (\n"]
    for alias in names:
        rendered = alias.name + (f" as {alias.asname}" if alias.asname else "")
        rows.append(f"    {rendered},\n")
    rows.append(")\n")
    return "".join(rows)


def is_app_binding(node: ast.AST, source_name: str | None = None) -> bool:
    if not isinstance(node, ast.Assign) or len(node.targets) != 1:
        return False
    target = node.targets[0]
    if not (
        isinstance(target, ast.Attribute)
        and isinstance(target.value, ast.Name)
        and target.value.id == "App"
        and target.attr == "_build_collectors_tab"
        and isinstance(node.value, ast.Name)
    ):
        return False
    return source_name is None or node.value.id == source_name


def is_name_binding(node: ast.AST, target_name: str) -> bool:
    return (
        isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == target_name
    )


def top_functions(tree: ast.Module, name: str) -> list[ast.FunctionDef]:
    return [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name]


def clean_desktop() -> tuple[int, int]:
    text = DESKTOP.read_text(encoding="utf-8")
    tree = ast.parse(text)
    replacements: list[tuple[int, int, str]] = []

    builders = top_functions(tree, LEGACY_BUILDER)
    if not builders:
        raise AssertionError((LEGACY_BUILDER, 0))
    builder_lines = sum(node.end_lineno - node.lineno + 1 for node in builders)
    if builder_lines < 300:
        raise AssertionError(("legacy_builder_lines", builder_lines))
    replacements.extend(replacement_span(text, node) for node in builders)

    old_button_defs = top_functions(tree, LEGACY_BUTTON)
    old_button_lines = sum(node.end_lineno - node.lineno + 1 for node in old_button_defs)
    replacements.extend(replacement_span(text, node) for node in old_button_defs)

    for node in ast.walk(tree):
        if is_app_binding(node, LEGACY_BUILDER) or is_name_binding(node, LEGACY_BUTTON):
            replacements.append(replacement_span(text, node))

    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or node.module != "spina_app.ui_controls":
            continue
        if not any(alias.name == LEGACY_BUTTON for alias in node.names):
            continue
        kept = [alias for alias in node.names if alias.name != LEGACY_BUTTON]
        replacements.append(replacement_span(text, node, import_source(node.module, kept)))

    updated = apply_replacements(text, replacements)
    updated_tree = ast.parse(updated)

    if top_functions(updated_tree, LEGACY_BUILDER) or top_functions(updated_tree, LEGACY_BUTTON):
        raise AssertionError("legacy desktop definitions survived replacement")
    remaining_loads = [
        node.id for node in ast.walk(updated_tree)
        if isinstance(node, ast.Name)
        and isinstance(node.ctx, ast.Load)
        and node.id in {LEGACY_BUILDER, LEGACY_BUTTON}
    ]
    if remaining_loads:
        raise AssertionError(("remaining_legacy_loads", remaining_loads))

    bindings = sorted(
        [node for node in ast.walk(updated_tree) if is_app_binding(node)],
        key=lambda node: node.lineno,
    )
    if not bindings or not isinstance(bindings[-1].value, ast.Name) or bindings[-1].value.id != ACTIVE_BUILDER:
        raise AssertionError(("final_collector_binding", [getattr(node.value, "id", "") for node in bindings]))

    DESKTOP.write_text(updated, encoding="utf-8")
    return builder_lines, old_button_lines


def clean_ui_controls() -> int:
    text = UI_CONTROLS.read_text(encoding="utf-8")
    tree = ast.parse(text)
    replacements: list[tuple[int, int, str]] = []

    old_buttons = top_functions(tree, LEGACY_BUTTON)
    if not old_buttons:
        raise AssertionError((LEGACY_BUTTON, 0))
    button_lines = sum(node.end_lineno - node.lineno + 1 for node in old_buttons)
    if button_lines < 20:
        raise AssertionError(("legacy_button_lines", button_lines))
    replacements.extend(replacement_span(text, node) for node in old_buttons)

    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or node.module != "spina_app.theme_palettes":
            continue
        if not any(alias.name == "_spina_v25_collector_colors" and alias.asname is None for alias in node.names):
            continue
        kept = [
            alias for alias in node.names
            if not (alias.name == "_spina_v25_collector_colors" and alias.asname is None)
        ]
        replacements.append(replacement_span(text, node, import_source(node.module, kept)))

    updated = apply_replacements(text, replacements)
    updated_tree = ast.parse(updated)
    if top_functions(updated_tree, LEGACY_BUTTON):
        raise AssertionError("legacy UI button survived replacement")
    if len(top_functions(updated_tree, ACTIVE_ROUTE_BUTTON)) != 1:
        raise AssertionError("active route button changed")
    if len(top_functions(updated_tree, ACTIVE_LOGIN_BUTTON)) != 1:
        raise AssertionError("active login button changed")

    UI_CONTROLS.write_text(updated, encoding="utf-8")
    return button_lines


def main() -> None:
    builder_lines, desktop_button_lines = clean_desktop()
    module_button_lines = clean_ui_controls()
    if desktop_button_lines:
        raise AssertionError(("unexpected_desktop_button_lines", desktop_button_lines))
    print(
        "Wave 52 cleanup applied:",
        f"{builder_lines} legacy builder lines + {module_button_lines} unused button lines removed.",
    )


if __name__ == "__main__":
    try:
        main()
        DIAGNOSTIC.unlink(missing_ok=True)
    except Exception:
        report = traceback.format_exc()
        DIAGNOSTIC.write_text(report, encoding="utf-8")
        print(report)
