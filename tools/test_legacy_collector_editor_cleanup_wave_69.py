from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "collector_dialog_presentation.py"
TARGET = '_collector_editor_dialog'
ACTIVE_TARGET = '_spina_v27_collector_editor_dialog'
ACTIVE_BINDING = 'App._collector_editor_dialog = _spina_v27_collector_editor_dialog'
CONFIGURE_CALL = '_configure_wave43_collector_dialog(globals())'
EXPECTED_CALLERS = ['_add_collector', '_edit_selected_collector']


def main() -> None:
    desktop_text = DESKTOP.read_text(encoding="utf-8")
    tree = ast.parse(desktop_text, filename=str(DESKTOP))
    app = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "App")

    legacy = [
        node for node in app.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == TARGET
    ]
    assert not legacy, legacy
    assert desktop_text.count(ACTIVE_BINDING) == 1
    assert CONFIGURE_CALL in desktop_text

    callers = []
    for method in app.body:
        if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(method):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == TARGET
                and isinstance(func.value, ast.Name)
                and func.value.id == "self"
            ):
                callers.append(method.name)
                break
    assert sorted(callers) == EXPECTED_CALLERS, callers

    binding_line = desktop_text[:desktop_text.index(ACTIVE_BINDING)].count("\n") + 1
    main_guards = [
        node for node in tree.body
        if isinstance(node, ast.If) and "__name__" in ast.unparse(node.test) and "__main__" in ast.unparse(node.test)
    ]
    assert main_guards, "Top-level main guard missing"
    assert binding_line < main_guards[-1].lineno

    spec = importlib.util.spec_from_file_location("wave69_collector_dialog", MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert callable(getattr(module, ACTIVE_TARGET))
    assert callable(module.configure_collector_dialog_dependencies)

    assert "Unified editor for Collector name + route areas + notes." not in desktop_text
    print("Wave 69 legacy collector editor cleanup regression passed:", EXPECTED_CALLERS)


if __name__ == "__main__":
    main()
