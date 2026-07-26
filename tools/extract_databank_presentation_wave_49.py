from __future__ import annotations

import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "databank_presentation.py"

TARGETS = (
    "_spina_v15_palette",
    "_spina_v15_setup_databank_styles",
    "_spina_v15_stat_card",
    "_spina_v15_build_data_tab",
    "_spina_v15_update_databank_cards",
    "_spina_v15_refresh_data_grid",
    "_spina_v15_update_data_toolbar",
    "_spina_v15_apply_ui_theme",
    "_spina_v16_apply_bigger_payment_grid",
    "_spina_v16_refresh_data_grid",
)
EXPECTED_LINES = {
    "_spina_v15_palette": 17,
    "_spina_v15_setup_databank_styles": 48,
    "_spina_v15_stat_card": 5,
    "_spina_v15_build_data_tab": 136,
    "_spina_v15_update_databank_cards": 39,
    "_spina_v15_refresh_data_grid": 18,
    "_spina_v15_update_data_toolbar": 7,
    "_spina_v15_apply_ui_theme": 11,
    "_spina_v16_apply_bigger_payment_grid": 21,
    "_spina_v16_refresh_data_grid": 7,
}
EXPECTED_HASHES = {
    "_spina_v15_palette": "a3f62850e60b84110fe96e601061be175730d07a7df1a273c64a2628a49eb037",
    "_spina_v15_setup_databank_styles": "55f92454aaf29af7e3f2a8995769ff109a9153c50835132a337bac5e86248212",
    "_spina_v15_stat_card": "44552d9fec3486c45f7e5f56aed237dd3cf035bd55ae0219b7f34cd46ad75657",
    "_spina_v15_build_data_tab": "06715b426fc112b66bf2cfca76ed844f7b5544276d6e9c867b6656e6b2c211ad",
    "_spina_v15_update_databank_cards": "ceaf5045cfade6235e8acfceee400ddf2211b89f09e364d257938fbc543e1780",
    "_spina_v15_refresh_data_grid": "8c2bc3d43da89ca2f770f5f03c5af71356d38cb2d32eac1cce72a0c27b4b0441",
    "_spina_v15_update_data_toolbar": "567bf6416e53cc0e9543227e37540d07308a43e192a2495e09693580ebef6632",
    "_spina_v15_apply_ui_theme": "cf7b8980b2617457ff3d40aa543c1c0f80cbfe60c951611fe3cf2beedc52ac9a",
    "_spina_v16_apply_bigger_payment_grid": "38daa05d54931f818a0252ec98bb84d8fd92aec332f7cd3aa87cfeacac9c6d97",
    "_spina_v16_refresh_data_grid": "0de5180c884ed6c8c2e6168efe7a8d8d4891b738f17ba1b9cbd404108e6e82ff",
}
EXPECTED_SIGNATURES = {
    "_spina_v15_palette": "self",
    "_spina_v15_setup_databank_styles": "self",
    "_spina_v15_stat_card": "parent, title, textvar",
    "_spina_v15_build_data_tab": "self",
    "_spina_v15_update_databank_cards": "self",
    "_spina_v15_refresh_data_grid": "self, *args, **kwargs",
    "_spina_v15_update_data_toolbar": "self, *args, **kwargs",
    "_spina_v15_apply_ui_theme": "self, *args, **kwargs",
    "_spina_v16_apply_bigger_payment_grid": "self",
    "_spina_v16_refresh_data_grid": "self, *args, **kwargs",
}
EXPECTED_CALLS = {
    "_spina_v15_palette": ["getattr", "isinstance", "lower", "self._theme_palette", "startswith", "str"],
    "_spina_v15_setup_databank_styles": ["_log_suppressed_once", "_spina_v15_palette", "getattr", "lower", "p.get", "st.configure", "st.map", "startswith", "str", "ttk.Style"],
    "_spina_v15_stat_card": ["pack", "ttk.Frame", "ttk.Label"],
    "_spina_v15_build_data_tab": ["_spina_v15_palette", "_spina_v15_setup_databank_styles", "_spina_v15_stat_card", "_spina_v15_update_databank_cards", "actions.pack", "body_card.pack", "c.grid", "child.destroy", "enumerate", "frm.configure", "frm.winfo_children", "getattr", "grid_head.pack", "hasattr", "header.pack", "left.pack", "left_actions.pack", "lower", "nav.pack", "nav_row.pack", "p.get", "pack", "page.pack", "range", "right_actions.pack", "search_box.pack", "search_row.pack", "self._mode_filter", "self._month_label", "self._update_data_toolbar", "self.db_search_entry.bind", "self.db_search_entry.pack", "self.inner.pack", "self.month_lbl.pack", "self.refresh_data_grid", "self.search_db_var.set", "self.search_db_var.trace_add", "startswith", "stats.grid_columnconfigure", "stats.pack", "str", "tk.StringVar", "ttk.Button", "ttk.Entry", "ttk.Frame", "ttk.Label"],
    "_spina_v15_update_databank_cards": ["_log_suppressed_once", "get", "getattr", "hasattr", "self._db_card_clients_var.set", "self._db_card_close_var.set", "self._db_card_month_var.set", "self._db_card_view_var.set", "self._mode_filter", "self._month_label", "str", "strip", "tv.get_children", "tv.item"],
    "_spina_v15_refresh_data_grid": ["_spina_v15_orig_refresh_data_grid", "_spina_v15_setup_databank_styles", "_spina_v15_update_databank_cards", "getattr", "self.days_tree.configure", "self.name_tree.configure"],
    "_spina_v15_update_data_toolbar": ["_spina_v15_orig_update_data_toolbar", "_spina_v15_update_databank_cards"],
    "_spina_v15_apply_ui_theme": ["_spina_v15_orig_apply_theme", "_spina_v15_setup_databank_styles", "_spina_v15_update_databank_cards"],
    "_spina_v16_apply_bigger_payment_grid": ["_spina_v15_setup_databank_styles", "getattr", "self.days_tree.column", "self.days_tree.configure", "self.name_tree.column", "self.name_tree.configure", "startswith", "str"],
    "_spina_v16_refresh_data_grid": ["_spina_v16_apply_bigger_payment_grid", "_spina_v16_prev_refresh_data_grid"],
}
PROTECTED_NEIGHBOR = ("_spina_v17_on_mode_change", "55b989eb84a2ba0c935bd017577ccba3c525e9b23620904f2cc1444fed091d86")
CAPTURES = {
    "_spina_v15_orig_refresh_data_grid": "refresh_data_grid",
    "_spina_v15_orig_update_data_toolbar": "_update_data_toolbar",
    "_spina_v15_orig_apply_theme": "_apply_ui_theme",
    "_spina_v16_prev_refresh_data_grid": "refresh_data_grid",
}
CAPTURE_BINDINGS = {
    "_spina_v15_orig_refresh_data_grid": ("refresh_data_grid", "_spina_v15_refresh_data_grid"),
    "_spina_v15_orig_update_data_toolbar": ("_update_data_toolbar", "_spina_v15_update_data_toolbar"),
    "_spina_v15_orig_apply_theme": ("_apply_ui_theme", "_spina_v15_apply_ui_theme"),
    "_spina_v16_prev_refresh_data_grid": ("refresh_data_grid", "_spina_v16_refresh_data_grid"),
}
DIRECT_BINDINGS = {
    "_build_data_tab": "_spina_v15_build_data_tab",
    "_setup_databank_styles": "_spina_v15_setup_databank_styles",
    "_update_databank_summary_cards": "_spina_v15_update_databank_cards",
}


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def source_for(lines: list[str], node: ast.AST) -> str:
    end = getattr(node, "end_lineno", None) or node.lineno
    return "\n".join(lines[node.lineno - 1:end])


def normalized(source: str) -> str:
    return "\n".join(line.rstrip() for line in source.strip().splitlines())


def source_hash(source: str) -> str:
    return hashlib.sha256(normalized(source).encode("utf-8")).hexdigest()


def functions(tree: ast.AST, name: str) -> list[ast.FunctionDef]:
    return [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name]


def calls_for(node: ast.FunctionDef) -> list[str]:
    return sorted({
        dotted(call.func)
        for call in ast.walk(node)
        if isinstance(call, ast.Call) and dotted(call.func)
    })


def capture_node(tree: ast.AST, name: str, attr: str) -> ast.Assign:
    matches = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        value = node.value
        if not isinstance(target, ast.Name) or target.id != name:
            continue
        if not isinstance(value, ast.Call) or not isinstance(value.func, ast.Name) or value.func.id != "getattr":
            continue
        if len(value.args) < 2:
            continue
        if not isinstance(value.args[0], ast.Name) or value.args[0].id != "App":
            continue
        if not isinstance(value.args[1], ast.Constant) or value.args[1].value != attr:
            continue
        matches.append(node)
    assert len(matches) == 1, (name, len(matches))
    return matches[0]


def binding_node(tree: ast.AST, attr: str, value_name: str) -> ast.Assign:
    matches = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "App"
            and target.attr == attr
            and isinstance(node.value, ast.Name)
            and node.value.id == value_name
        ):
            matches.append(node)
    assert len(matches) == 1, (attr, value_name, len(matches))
    return matches[0]


def indent_for(lines: list[str], lineno: int) -> str:
    line = lines[lineno - 1]
    return line[: len(line) - len(line.lstrip())]


def make_module(sources: dict[str, str]) -> str:
    header = '''"""Data Bank presentation extracted in Wave 49."""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk

_DATABANK_PRESENTATION_DEPENDENCIES = {}
_PROTECTED_GLOBALS = {
    "__builtins__", "__cached__", "__doc__", "__file__", "__loader__",
    "__name__", "__package__", "__spec__", "os", "tk", "ttk",
    "_DATABANK_PRESENTATION_DEPENDENCIES", "_PROTECTED_GLOBALS",
    "configure_databank_presentation_dependencies",
    "DATABANK_PRESENTATION_TARGETS", "DATABANK_PRESENTATION_SOURCE_LINES",
    "DATABANK_PRESENTATION_SOURCE_SHA256", "DATABANK_PRESENTATION_SIGNATURES",
    "DATABANK_PRESENTATION_CALLS", "DATABANK_PRESENTATION_TOTAL_SOURCE_LINES",
    "_spina_v15_palette", "_spina_v15_setup_databank_styles",
    "_spina_v15_stat_card", "_spina_v15_build_data_tab",
    "_spina_v15_update_databank_cards", "_spina_v15_refresh_data_grid",
    "_spina_v15_update_data_toolbar", "_spina_v15_apply_ui_theme",
    "_spina_v16_apply_bigger_payment_grid", "_spina_v16_refresh_data_grid",
}


def configure_databank_presentation_dependencies(namespace):
    _DATABANK_PRESENTATION_DEPENDENCIES.clear()
    _DATABANK_PRESENTATION_DEPENDENCIES.update(namespace)
    for name, value in namespace.items():
        if name not in _PROTECTED_GLOBALS:
            globals()[name] = value

'''
    metadata = (
        f"DATABANK_PRESENTATION_TARGETS = {list(TARGETS)!r}\n"
        f"DATABANK_PRESENTATION_SOURCE_LINES = {EXPECTED_LINES!r}\n"
        f"DATABANK_PRESENTATION_SOURCE_SHA256 = {EXPECTED_HASHES!r}\n"
        f"DATABANK_PRESENTATION_SIGNATURES = {EXPECTED_SIGNATURES!r}\n"
        f"DATABANK_PRESENTATION_CALLS = {EXPECTED_CALLS!r}\n"
        f"DATABANK_PRESENTATION_TOTAL_SOURCE_LINES = {sum(EXPECTED_LINES.values())}\n\n"
    )
    body = "\n\n".join(normalized(sources[name]) for name in TARGETS) + "\n"
    result = header + metadata + body
    ast.parse(result)
    return result


def main() -> None:
    assert not MODULE.exists(), MODULE

    text = DESKTOP.read_text(encoding="utf-8")
    lines = text.splitlines()
    newline = "\r\n" if "\r\n" in text else "\n"
    tree = ast.parse(text)

    sources: dict[str, str] = {}
    nodes: dict[str, ast.FunctionDef] = {}
    for name in TARGETS:
        matches = functions(tree, name)
        assert len(matches) == 1, (name, len(matches))
        node = matches[0]
        source = source_for(lines, node)
        assert len(normalized(source).splitlines()) == EXPECTED_LINES[name]
        assert source_hash(source) == EXPECTED_HASHES[name]
        assert ast.unparse(node.args) == EXPECTED_SIGNATURES[name]
        assert calls_for(node) == EXPECTED_CALLS[name], (name, calls_for(node))
        sources[name] = source
        nodes[name] = node

    neighbor_name, neighbor_hash = PROTECTED_NEIGHBOR
    neighbor = functions(tree, neighbor_name)
    assert len(neighbor) == 1
    assert source_hash(source_for(lines, neighbor[0])) == neighbor_hash

    captures = {
        name: capture_node(tree, name, attr)
        for name, attr in CAPTURES.items()
    }
    for capture_name, (attr, wrapper) in CAPTURE_BINDINGS.items():
        capture = captures[capture_name]
        binding = binding_node(tree, attr, wrapper)
        assert capture.lineno < binding.lineno
    for attr, value_name in DIRECT_BINDINGS.items():
        binding_node(tree, attr, value_name)

    first = nodes[TARGETS[0]]
    first_indent = indent_for(lines, first.lineno)
    import_block = [
        first_indent + "from spina_app.databank_presentation import (",
        first_indent + "    configure_databank_presentation_dependencies as _wave49_configure_databank_presentation_dependencies,",
    ]
    for name in TARGETS:
        import_block.append(first_indent + f"    {name} as _wave49{name},")
    import_block.append(first_indent + ")")
    for name in TARGETS:
        import_block.append(first_indent + f"{name} = _wave49{name}")
    import_block.append(first_indent + "_wave49_configure_databank_presentation_dependencies(globals())")

    edits: list[tuple[int, int, list[str]]] = [
        (first.lineno - 1, first.end_lineno, import_block)
    ]
    for name in TARGETS[1:]:
        node = nodes[name]
        edits.append((node.lineno - 1, node.end_lineno, []))
    for capture in captures.values():
        indent = indent_for(lines, capture.lineno)
        edits.append((capture.end_lineno, capture.end_lineno, [
            indent + "_wave49_configure_databank_presentation_dependencies(globals())"
        ]))

    for start, end, replacement in sorted(edits, key=lambda item: (item[0], item[1]), reverse=True):
        lines[start:end] = replacement

    updated = newline.join(lines) + (newline if text.endswith(("\n", "\r\n")) else "")
    updated_tree = ast.parse(updated)
    updated_lines = updated.splitlines()
    for name in TARGETS:
        assert not functions(updated_tree, name), name

    imports = [
        node for node in ast.walk(updated_tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "spina_app.databank_presentation"
    ]
    assert len(imports) == 1
    aliases = {(item.name, item.asname) for item in imports[0].names}
    assert ("configure_databank_presentation_dependencies", "_wave49_configure_databank_presentation_dependencies") in aliases
    for name in TARGETS:
        assert (name, "_wave49" + name) in aliases

    configure_lines = [
        node.lineno for node in ast.walk(updated_tree)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "_wave49_configure_databank_presentation_dependencies"
    ]
    assert len(configure_lines) == 5, configure_lines

    for capture_name, attr in CAPTURES.items():
        capture = capture_node(updated_tree, capture_name, attr)
        binding_attr, wrapper = CAPTURE_BINDINGS[capture_name]
        binding = binding_node(updated_tree, binding_attr, wrapper)
        assert any(capture.lineno < line < binding.lineno for line in configure_lines), capture_name
    for attr, value_name in DIRECT_BINDINGS.items():
        binding_node(updated_tree, attr, value_name)

    neighbor = functions(updated_tree, neighbor_name)
    assert len(neighbor) == 1
    assert source_hash(source_for(updated_lines, neighbor[0])) == neighbor_hash

    module_source = make_module(sources)
    DESKTOP.write_text(updated, encoding="utf-8", newline="")
    MODULE.write_text(module_source, encoding="utf-8")
    print("Prepared guarded Wave 49 Data Bank extraction: 10 helpers, 309 lines.")


if __name__ == "__main__":
    main()
