from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
UI_CONTROLS = ROOT / "spina_app" / "ui_controls.py"

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
    for start, end, replacement in sorted(replacements, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text


def import_source(module: str, names: list[ast.alias]) -> str:
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


def is_app_binding(node: ast.AST, source_name: str) -> bool:
    if not isinstance(node, ast.Assign) or len(node.targets) != 1:
        return False
    target = node.targets[0]
    return (
        isinstance(target, ast.Attribute)
        and isinstance(target.value, ast.Name)
        and target.value.id == "App"
        and target.attr == "_build_collectors_tab"
        and isinstance(node.value, ast.Name)
        and node.value.id == source_name
    )


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
    assert len(builders) == 1, (LEGACY_BUILDER, len(builders))
    builder_lines = builders[0].end_lineno - builders[0].lineno + 1
    assert builder_lines == 346, builder_lines
    replacements.append(replacement_span(text, builders[0]))

    old_button_defs = top_functions(tree, LEGACY_BUTTON)
    assert len(old_button_defs) <= 1
    old_button_lines = 0
    if old_button_defs:
        old_button_lines = old_button_defs[0].end_lineno - old_button_defs[0].lineno + 1
        replacements.append(replacement_span(text, old_button_defs[0]))

    old_app_bindings = [node for node in tree.body if is_app_binding(node, LEGACY_BUILDER)]
    assert len(old_app_bindings) == 1, len(old_app_bindings)
    replacements.append(replacement_span(text, old_app_bindings[0]))

    old_name_bindings = [node for node in tree.body if is_name_binding(node, LEGACY_BUTTON)]
    assert len(old_name_bindings) <= 1, len(old_name_bindings)
    for node in old_name_bindings:
        replacements.append(replacement_span(text, node))

    button_imports = [
        node for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "spina_app.ui_controls"
        and any(alias.name == LEGACY_BUTTON for alias in node.names)
    ]
    assert len(button_imports) == 1, len(button_imports)
    node = button_imports[0]
    kept = [alias for alias in node.names if alias.name != LEGACY_BUTTON]
    assert kept, "Wave 52 must preserve active UI-control imports"
    replacements.append(replacement_span(text, node, import_source(node.module, kept)))

    updated = apply_replacements(text, replacements)
    updated_tree = ast.parse(updated)

    assert not top_functions(updated_tree, LEGACY_BUILDER)
    assert not top_functions(updated_tree, LEGACY_BUTTON)
    assert not [node for node in ast.walk(updated_tree) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in {LEGACY_BUILDER, LEGACY_BUTTON}]

    active_builders = top_functions(updated_tree, ACTIVE_BUILDER)
    assert not active_builders, "Active builder must remain extracted in spina_app.collector_tab_presentation"
    active_bindings = [node for node in updated_tree.body if is_app_binding(node, ACTIVE_BUILDER)]
    assert len(active_bindings) == 1, len(active_bindings)

    DESKTOP.write_text(updated, encoding="utf-8")
    return builder_lines, old_button_lines


def clean_ui_controls() -> int:
    text = UI_CONTROLS.read_text(encoding="utf-8")
    tree = ast.parse(text)
    replacements: list[tuple[int, int, str]] = []

    old_buttons = top_functions(tree, LEGACY_BUTTON)
    assert len(old_buttons) == 1, (LEGACY_BUTTON, len(old_buttons))
    button_lines = old_buttons[0].end_lineno - old_buttons[0].lineno + 1
    assert button_lines == 29, button_lines
    replacements.append(replacement_span(text, old_buttons[0]))

    palette_imports = [
        node for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "spina_app.theme_palettes"
        and any(alias.name == "_spina_v25_collector_colors" and alias.asname is None for alias in node.names)
    ]
    assert len(palette_imports) == 1, len(palette_imports)
    node = palette_imports[0]
    kept = [
        alias for alias in node.names
        if not (alias.name == "_spina_v25_collector_colors" and alias.asname is None)
    ]
    replacements.append(replacement_span(text, node, import_source(node.module, kept)))

    updated = apply_replacements(text, replacements)
    updated_tree = ast.parse(updated)
    assert not top_functions(updated_tree, LEGACY_BUTTON)
    assert len(top_functions(updated_tree, ACTIVE_ROUTE_BUTTON)) == 1
    assert len(top_functions(updated_tree, ACTIVE_LOGIN_BUTTON)) == 1

    UI_CONTROLS.write_text(updated, encoding="utf-8")
    return button_lines


def main() -> None:
    builder_lines, desktop_button_lines = clean_desktop()
    module_button_lines = clean_ui_controls()
    assert desktop_button_lines == 0, desktop_button_lines
    assert builder_lines + module_button_lines == 375
    print(
        "Wave 52 cleanup applied:",
        f"{builder_lines} legacy builder lines + {module_button_lines} unused button lines removed.",
    )


if __name__ == "__main__":
    main()
