"""Regression checks for Dashboard visibility Wave 24."""

from __future__ import annotations

import ast
import hashlib
import importlib
from pathlib import Path

SOURCE = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
MODULE = Path("spina_app/tabs/dashboard.py")
TARGETS = {'_spina_dashboard_visible_rows': '4c8d9a40a9119ee422f66de37bdcacf222953ee7e7c606180a52996814b88457', '_spina_v19_visible_dashboard_rows': '6ff49ee1c41c7b340ca62f58ed09bbe05a16118f791626b5d85946e7db6515ae', '_spina_v20_visible_rows': 'b4f184c6ae909b0cb1a1d4053306e4bc19a08aa52fac8d2cb45dea3b965a1a6a'}
MARKER = '\n# Dashboard visibility filters extracted in Wave 24.\n\n'
ORIGINAL_MODULE_SHA256 = '569dcd6b0dd8ef9864d3e738ae87e2b43873ae369ee6cac73870182dcdf908dc'


def source_for(lines: list[str], node: ast.AST) -> str:
    return "\n".join(lines[node.lineno - 1 : node.end_lineno])


class Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class Dummy:
    pass


def sample_rows():
    return [
        {"name": "Ana Cruz", "area": "East", "loan_type": "Regular", "status": "Finishing Now"},
        {"name": "Ben Santos", "area": "West", "loan_type": "7x7", "status": "Active"},
        {"name": "Cara Reyes", "area": "North", "loan_type": "Regular", "status": "Overdue"},
    ]


def make_dummy(*, loan="All", status="All Active", search=""):
    obj = Dummy()
    obj._dashboard_rows = sample_rows()
    obj.dashboard_loan_filter_var = Var(loan)
    obj.dashboard_status_filter_var = Var(status)
    obj.dashboard_search_var = Var(search)
    return obj


def main() -> None:
    app_text = SOURCE.read_text(encoding="utf-8")
    app_tree = ast.parse(app_text, filename=str(SOURCE))
    remaining = {
        node.name
        for node in app_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in TARGETS
    }
    assert not remaining, f"Definitions still remain in desktop source: {sorted(remaining)}"

    imported = set()
    for node in app_tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "spina_app.tabs.dashboard":
            imported.update(alias.name for alias in node.names)
    assert set(TARGETS).issubset(imported), f"Dashboard imports missing: {sorted(set(TARGETS) - imported)}"

    module_text = MODULE.read_text(encoding="utf-8")
    assert module_text.count(MARKER) == 1, "Wave 24 marker missing or duplicated"
    base_text, _extracted_text = module_text.split(MARKER, 1)
    base_sha = hashlib.sha256(base_text.encode("utf-8")).hexdigest()
    assert base_sha == ORIGINAL_MODULE_SHA256, f"Pre-existing Dashboard module changed: {base_sha}"

    module_lines = module_text.splitlines()
    module_tree = ast.parse(module_text, filename=str(MODULE))
    module_nodes = {
        node.name: node
        for node in module_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in TARGETS
    }
    assert set(module_nodes) == set(TARGETS), f"Module definitions differ: {sorted(module_nodes)}"

    for name, expected_hash in TARGETS.items():
        source = source_for(module_lines, module_nodes[name])
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        assert digest == expected_hash, f"Source changed for {name}: {digest}"

    module = importlib.import_module("spina_app.tabs.dashboard")
    module.tk.StringVar = lambda value="": Var(value)
    for name in TARGETS:
        assert callable(getattr(module, name, None)), f"{name} is not callable after import"

    rows = module._spina_v19_visible_dashboard_rows(make_dummy())
    assert len(rows) == 3, "All Active should keep every loaded row"

    priority = module._spina_v19_visible_dashboard_rows(make_dummy(status="Priority"))
    assert [row["name"] for row in priority] == ["Ana Cruz", "Cara Reyes"]

    seven = module._spina_v19_visible_dashboard_rows(make_dummy(loan="7x7"))
    assert [row["name"] for row in seven] == ["Ben Santos"]

    searched = module._spina_v19_visible_dashboard_rows(make_dummy(search="overdue"))
    assert [row["name"] for row in searched] == ["Cara Reyes"]

    old_priority = module._spina_dashboard_visible_rows(make_dummy(status="Finishing Priority"))
    assert [row["name"] for row in old_priority] == ["Ana Cruz", "Cara Reyes"]

    wrapped = module._spina_v20_visible_rows(make_dummy(status="Priority"))
    assert wrapped == priority, "v20 wrapper must preserve v19 behavior"

    print("Dashboard visibility Wave 24 regression passed.")


if __name__ == "__main__":
    main()
