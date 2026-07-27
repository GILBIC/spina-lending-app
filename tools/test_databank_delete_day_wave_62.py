"""Permanent structural regression for Delete Day after the Wave 63 password-gate fix."""
from __future__ import annotations

import ast
import hashlib
import importlib
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE_PATH = ROOT / "spina_app" / "databank_delete_day.py"
PROTECTED_WAVE61 = [
    "App._save_cell_edit = _wave61_save_cell_edit",
    "App.delete_selected_cell = _wave61_delete_selected_cell",
    "App._mark_missed_for_selected = _wave61_mark_missed_for_selected",
]


def sha(source: str) -> str:
    return hashlib.sha256(source.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def dotted(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return None


def main() -> None:
    module_text = MODULE_PATH.read_text(encoding="utf-8")
    module_lines = module_text.splitlines(keepends=True)
    module_tree = ast.parse(module_text)
    functions = {node.name: node for node in module_tree.body if isinstance(node, ast.FunctionDef)}
    node = functions["open_delete_day_dialog"]
    source = "".join(module_lines[node.lineno - 1:node.end_lineno])
    calls = sorted({
        value
        for child in ast.walk(node)
        if isinstance(child, ast.Call)
        for value in [dotted(child.func)]
        if value
    })
    strings = sorted({
        child.value
        for child in ast.walk(node)
        if isinstance(child, ast.Constant) and isinstance(child.value, str)
    })

    imported = importlib.import_module("spina_app.databank_delete_day")
    metadata = imported.DATABANK_DELETE_DAY_METHOD
    assert node.end_lineno - node.lineno + 1 == metadata["lines"]
    assert sha(textwrap.dedent(source)) == metadata["dedented_sha256"]
    assert sha(source) == metadata["source_sha256"]
    assert ast.unparse(node.args) == metadata["signature"] == "self"
    assert calls == metadata["calls"]
    assert sorted(call for call in calls if call.startswith("self.db.")) == metadata["db_calls"]
    assert strings == metadata["strings"]
    assert "Password verification failed:\n" in strings

    password_try = next(
        child for child in node.body
        if isinstance(child, ast.Try)
        and any(dotted(call.func) == "self._prompt_current_password"
                for call in ast.walk(child) if isinstance(call, ast.Call))
    )
    assert password_try.handlers
    handler = password_try.handlers[0]
    assert not any(
        isinstance(child, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "ok" for target in child.targets)
        and isinstance(child.value, ast.Constant)
        and child.value.value is True
        for child in ast.walk(handler)
    )
    assert any(isinstance(child, ast.Return) for child in ast.walk(handler))

    app_text = APP_PATH.read_text(encoding="utf-8")
    app_tree = ast.parse(app_text)
    app_class = next(node for node in app_tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    app_methods = {node.name for node in app_class.body if isinstance(node, ast.FunctionDef)}
    assert "open_delete_day_dialog" not in app_methods
    assert app_text.count(
        "configure_databank_delete_day_dependencies as _configure_wave62_databank_delete_day"
    ) == 1
    assert app_text.count("App.open_delete_day_dialog = _wave62_open_delete_day_dialog") == 1
    for marker in PROTECTED_WAVE61:
        assert app_text.count(marker) == 1

    print("Delete Day structural regression passed:", metadata["lines"], "lines")


if __name__ == "__main__":
    main()
