from __future__ import annotations

import ast
import hashlib
import importlib
import re
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE_PATH = ROOT / "spina_app" / "databank_presentation.py"

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
PROTECTED_NEIGHBOR_HASH = "55b989eb84a2ba0c935bd017577ccba3c525e9b23620904f2cc1444fed091d86"
SQL_WRITE_RE = re.compile(r"\b(?:INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|ALTER\s+TABLE|DROP\s+TABLE|CREATE\s+TABLE)\b", re.I)
MUTATING_CALLS = {
    "connect_db", "run_write", "open", "Path", "execute", "executemany",
    "commit", "rollback", "write", "write_text", "write_bytes", "unlink",
    "mkdir", "makedirs", "remove", "rename", "replace", "copy", "copy2", "move",
}
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


def binding_nodes(tree: ast.AST, attr: str, value_name: str) -> list[ast.Assign]:
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
    return matches


def assert_presentation_only(node: ast.FunctionDef) -> None:
    for part in ast.walk(node):
        if isinstance(part, ast.Call):
            call = dotted(part.func)
            tail = call.rsplit(".", 1)[-1]
            assert call not in MUTATING_CALLS and tail not in MUTATING_CALLS, call
        if isinstance(part, ast.Name):
            assert part.id not in {"connect_db", "run_write", "Path", "open"}, part.id
        if isinstance(part, ast.Constant) and isinstance(part.value, str):
            assert not SQL_WRITE_RE.search(part.value), part.value


class FakeVar:
    def __init__(self, value=""):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value


class FakeTree:
    def __init__(self):
        self.rows = {"a": ("Client A", "Area 1"), "b": ("(no clients)", "")}
    def get_children(self):
        return list(self.rows)
    def item(self, iid, field):
        assert field == "values"
        return self.rows[iid]


def main() -> None:
    module = importlib.import_module("spina_app.databank_presentation")
    assert module.DATABANK_PRESENTATION_TARGETS == list(TARGETS)
    assert module.DATABANK_PRESENTATION_SOURCE_LINES == EXPECTED_LINES
    assert module.DATABANK_PRESENTATION_SOURCE_SHA256 == EXPECTED_HASHES
    assert module.DATABANK_PRESENTATION_SIGNATURES == EXPECTED_SIGNATURES
    assert module.DATABANK_PRESENTATION_CALLS == EXPECTED_CALLS
    assert module.DATABANK_PRESENTATION_TOTAL_SOURCE_LINES == 309

    module_text = MODULE_PATH.read_text(encoding="utf-8")
    module_lines = module_text.splitlines()
    module_tree = ast.parse(module_text)
    for name in TARGETS:
        matches = functions(module_tree, name)
        assert len(matches) == 1, (name, len(matches))
        node = matches[0]
        source = source_for(module_lines, node)
        assert len(normalized(source).splitlines()) == EXPECTED_LINES[name]
        assert source_hash(source) == EXPECTED_HASHES[name]
        assert ast.unparse(node.args) == EXPECTED_SIGNATURES[name]
        calls = sorted({dotted(call.func) for call in ast.walk(node) if isinstance(call, ast.Call) and dotted(call.func)})
        assert calls == EXPECTED_CALLS[name], (name, calls)
        assert_presentation_only(node)

    desktop_text = DESKTOP.read_text(encoding="utf-8")
    desktop_lines = desktop_text.splitlines()
    desktop_tree = ast.parse(desktop_text)
    for name in TARGETS:
        assert not functions(desktop_tree, name), name

    imports = [
        node for node in ast.walk(desktop_tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "spina_app.databank_presentation"
    ]
    assert len(imports) == 1
    aliases = {(item.name, item.asname) for item in imports[0].names}
    assert ("configure_databank_presentation_dependencies", "_wave49_configure_databank_presentation_dependencies") in aliases
    for name in TARGETS:
        assert (name, "_wave49" + name) in aliases

    symbol_rebinds = []
    configure_lines = []
    for node in ast.walk(desktop_tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id in TARGETS and isinstance(node.value, ast.Name):
                symbol_rebinds.append((target.id, node.value.id))
        if (
            isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "_wave49_configure_databank_presentation_dependencies"
        ):
            configure_lines.append(node.lineno)
    assert sorted(symbol_rebinds) == sorted((name, "_wave49" + name) for name in TARGETS)
    assert len(configure_lines) == 5, configure_lines

    for attr, value_name in DIRECT_BINDINGS.items():
        matches = binding_nodes(desktop_tree, attr, value_name)
        assert len(matches) == 1, (attr, value_name, len(matches))

    capture_positions = {}
    binding_positions = {}
    for capture_name, attr in CAPTURES.items():
        capture = capture_node(desktop_tree, capture_name, attr)
        binding_attr, wrapper = CAPTURE_BINDINGS[capture_name]
        bindings = binding_nodes(desktop_tree, binding_attr, wrapper)
        assert len(bindings) == 1, (capture_name, bindings)
        binding = bindings[0]
        assert capture.lineno < binding.lineno
        assert any(capture.lineno < line < binding.lineno for line in configure_lines), capture_name
        capture_positions[capture_name] = capture.lineno
        binding_positions[capture_name] = binding.lineno

    assert binding_positions["_spina_v15_orig_refresh_data_grid"] < capture_positions["_spina_v16_prev_refresh_data_grid"] < binding_positions["_spina_v16_prev_refresh_data_grid"]
    refresh_bindings = []
    for node in ast.walk(desktop_tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "App"
            and target.attr == "refresh_data_grid"
            and isinstance(node.value, ast.Name)
        ):
            refresh_bindings.append((node.lineno, node.value.id))
    refresh_bindings.sort()
    assert refresh_bindings[-1][1] == "_spina_v16_refresh_data_grid"

    neighbor = functions(desktop_tree, "_spina_v17_on_mode_change")
    assert len(neighbor) == 1
    assert source_hash(source_for(desktop_lines, neighbor[0])) == PROTECTED_NEIGHBOR_HASH

    fake = SimpleNamespace(
        _ui_colors={"bg": "x", "panel": "y"},
        _theme_palette=lambda: {"bg": "fallback"},
        ui_theme="light",
    )
    assert module._spina_v15_palette(fake) is fake._ui_colors

    card_fake = SimpleNamespace(
        name_tree=FakeTree(),
        _db_card_clients_var=FakeVar(),
        _db_card_view_var=FakeVar(),
        _db_card_month_var=FakeVar(),
        _db_card_close_var=FakeVar(),
        _db_close_info_var=FakeVar("Closed July 26"),
        _mode_filter=lambda: "Regular",
        _month_label=lambda: "July 2026",
    )
    module._spina_v15_update_databank_cards(card_fake)
    assert card_fake._db_card_clients_var.get() == "1 client"
    assert card_fake._db_card_view_var.get() == "Regular"
    assert card_fake._db_card_month_var.get() == "July 2026"
    assert card_fake._db_card_close_var.get() == "Closed July 26"

    events = []
    saved = {
        "refresh": getattr(module, "_spina_v15_orig_refresh_data_grid", None),
        "toolbar": getattr(module, "_spina_v15_orig_update_data_toolbar", None),
        "theme": getattr(module, "_spina_v15_orig_apply_theme", None),
        "prev": getattr(module, "_spina_v16_prev_refresh_data_grid", None),
        "styles": module._spina_v15_setup_databank_styles,
        "cards": module._spina_v15_update_databank_cards,
        "bigger": module._spina_v16_apply_bigger_payment_grid,
    }
    try:
        module._spina_v15_setup_databank_styles = lambda self: events.append("styles")
        module._spina_v15_update_databank_cards = lambda self: events.append("cards")
        module._spina_v16_apply_bigger_payment_grid = lambda self: events.append("bigger")
        module._spina_v15_orig_refresh_data_grid = lambda self, *a, **k: events.append("refresh") or "refresh-result"
        module._spina_v15_orig_update_data_toolbar = lambda self, *a, **k: events.append("toolbar") or "toolbar-result"
        module._spina_v15_orig_apply_theme = lambda self, *a, **k: events.append("theme") or "theme-result"
        module._spina_v16_prev_refresh_data_grid = lambda self, *a, **k: events.append("prev") or "prev-result"
        dummy = SimpleNamespace(name_tree=None, days_tree=None)

        assert module._spina_v15_refresh_data_grid(dummy) == "refresh-result"
        assert events == ["refresh", "styles", "cards"]
        events.clear()
        assert module._spina_v15_update_data_toolbar(dummy) == "toolbar-result"
        assert events == ["toolbar", "cards"]
        events.clear()
        assert module._spina_v15_apply_ui_theme(dummy) == "theme-result"
        assert events == ["theme", "styles", "cards"]
        events.clear()
        assert module._spina_v16_refresh_data_grid(dummy) == "prev-result"
        assert events == ["prev", "bigger"]
    finally:
        module._spina_v15_setup_databank_styles = saved["styles"]
        module._spina_v15_update_databank_cards = saved["cards"]
        module._spina_v16_apply_bigger_payment_grid = saved["bigger"]
        for key, name in (
            ("refresh", "_spina_v15_orig_refresh_data_grid"),
            ("toolbar", "_spina_v15_orig_update_data_toolbar"),
            ("theme", "_spina_v15_orig_apply_theme"),
            ("prev", "_spina_v16_prev_refresh_data_grid"),
        ):
            if saved[key] is None:
                module.__dict__.pop(name, None)
            else:
                module.__dict__[name] = saved[key]

    print("Wave 49 Data Bank presentation regression passed.")


if __name__ == "__main__":
    main()
