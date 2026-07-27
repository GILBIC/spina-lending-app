from __future__ import annotations

import ast
import hashlib
import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE_PATH = ROOT / "spina_app" / "audit_presentation.py"
TARGETS = ('_build_audit_tab', 'refresh_audit_tab')
EXPECTED = {'_build_audit_tab': {'lines': 70, 'sha256': 'd4e603a9c902e4eef8b198f3d3f421fa0e1405e37953e5cbe8a4960f78386d27', 'signature': 'self', 'calls': ['_date.today', 'detail_vsb.grid', 'details.columnconfigure', 'details.grid', 'details.rowconfigure', 'filters.columnconfigure', 'filters.grid', 'grid', 'outer.columnconfigure', 'outer.rowconfigure', 'range', 'self._audit_show_selected', 'self._audit_tree_factory', 'self.audit_detail_text.configure', 'self.audit_detail_text.grid', 'self.audit_nb.add', 'self.audit_nb.grid', 'self.audit_new_tree.bind', 'self.audit_renew_tree.bind', 'strftime', 'title.columnconfigure', 'title.grid', 'tk.StringVar', 'tk.Text', 'ttk.Button', 'ttk.Entry', 'ttk.Frame', 'ttk.Label', 'ttk.LabelFrame', 'ttk.Notebook', 'ttk.Scrollbar']}, 'refresh_audit_tab': {'lines': 113, 'sha256': '1a5a34adc75231b60cb235cbcd46be5ddee3718e5c49f6de2ba555952a08ce06', 'signature': 'self', 'calls': ['enumerate', 'float', 'iter', 'len', 'list', 'lower', 'next', 'r.get', 'row.get', 'self._audit_money_text', 'self._audit_new_rows_map.keys', 'self._audit_parse_date_filters', 'self._audit_renew_rows_map.keys', 'self._audit_set_detail_text', 'self._audit_show_selected', 'self.audit_name_var.get', 'self.audit_new_tree.delete', 'self.audit_new_tree.focus', 'self.audit_new_tree.get_children', 'self.audit_new_tree.insert', 'self.audit_new_tree.selection_set', 'self.audit_renew_tree.delete', 'self.audit_renew_tree.focus', 'self.audit_renew_tree.get_children', 'self.audit_renew_tree.insert', 'self.audit_renew_tree.selection_set', 'self.audit_summary_var.set', 'self.db.get_audit_new_loan_rows', 'self.db.get_audit_renewal_rows', 'str', 'strip']}}


def normalized(source: str) -> str:
    return "\n".join(line.rstrip() for line in source.strip().splitlines())


def source_hash(source: str) -> str:
    return hashlib.sha256(normalized(source).encode("utf-8")).hexdigest()


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def functions(tree: ast.AST, name: str):
    return [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name]


def main() -> None:
    module = importlib.import_module("spina_app.audit_presentation")
    assert module.AUDIT_PRESENTATION_TARGETS == list(TARGETS)
    assert module.AUDIT_PRESENTATION_TOTAL_SOURCE_LINES == 183
    assert module.AUDIT_PRESENTATION_SOURCE_LINES == {name: item["lines"] for name, item in EXPECTED.items()}
    assert module.AUDIT_PRESENTATION_SOURCE_SHA256 == {name: item["sha256"] for name, item in EXPECTED.items()}
    assert module.AUDIT_PRESENTATION_SIGNATURES == {name: item["signature"] for name, item in EXPECTED.items()}
    assert module.AUDIT_PRESENTATION_CALLS == {name: item["calls"] for name, item in EXPECTED.items()}

    module_text = MODULE_PATH.read_text(encoding="utf-8")
    module_lines = module_text.splitlines()
    module_tree = ast.parse(module_text)
    for name in TARGETS:
        matches = [node for node in module_tree.body if isinstance(node, ast.FunctionDef) and node.name == name]
        assert len(matches) == 1, (name, len(matches))
        node = matches[0]
        source = "\n".join(module_lines[node.lineno - 1 : node.end_lineno])
        assert len(normalized(source).splitlines()) == EXPECTED[name]["lines"]
        assert source_hash(source) == EXPECTED[name]["sha256"]
        assert ast.unparse(node.args) == EXPECTED[name]["signature"]
        calls = sorted({dotted(call.func) for call in ast.walk(node) if isinstance(call, ast.Call) and dotted(call.func)})
        assert calls == EXPECTED[name]["calls"], (name, calls)

    desktop_text = DESKTOP.read_text(encoding="utf-8")
    desktop_tree = ast.parse(desktop_text)
    app = next(node for node in desktop_tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    remaining = {node.name for node in app.body if isinstance(node, ast.FunctionDef)}
    assert not (set(TARGETS) & remaining), sorted(set(TARGETS) & remaining)

    imports = [
        node for node in desktop_tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "spina_app.audit_presentation"
    ]
    assert len(imports) == 1
    aliases = {(item.name, item.asname) for item in imports[0].names}
    assert ("configure_audit_presentation_dependencies", "_wave54_configure_audit_presentation_dependencies") in aliases
    for name in TARGETS:
        assert (name, "_wave54" + name) in aliases

    configure = [
        node for node in desktop_tree.body
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "_wave54_configure_audit_presentation_dependencies"
    ]
    assert len(configure) == 1

    bindings = []
    for node in desktop_tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if (
            isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name)
            and target.value.id == "App" and target.attr in TARGETS
            and isinstance(node.value, ast.Name)
        ):
            bindings.append((target.attr, node.value.id, node.lineno))
    assert sorted((name, value) for name, value, _ in bindings) == sorted((name, "_wave54" + name) for name in TARGETS)
    assert all(app.end_lineno < line for _, _, line in bindings)

    print("Wave 54 Audit presentation regression passed.")


if __name__ == "__main__":
    main()
