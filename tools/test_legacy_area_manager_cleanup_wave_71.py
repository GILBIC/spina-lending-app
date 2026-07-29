from __future__ import annotations

import ast
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE_PATH = ROOT / "spina_app" / "area_hierarchy_ui.py"
TARGET = "open_areas_manager"
EXPECTED_MODERN_AST_SHA256 = "3854a70a38acbcad2861b8f4866a81fc7fb6759fd92cfb59b49bb5ac55908359"
EXPECTED_MODERN_SIGNATURE = "app, parent=None"
EXPECTED_MODERN_LINES = 271
EXPECTED_BINDING_VALUE = "_spina_area_open_manager"


def signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    parts: list[str] = []
    positional = [*node.args.posonlyargs, *node.args.args]
    defaults = [None] * (len(positional) - len(node.args.defaults)) + list(node.args.defaults)
    for arg, default in zip(positional, defaults):
        text = arg.arg
        if default is not None:
            text += f"={ast.unparse(default)}"
        parts.append(text)
    if node.args.vararg:
        parts.append(f"*{node.args.vararg.arg}")
    elif node.args.kwonlyargs:
        parts.append("*")
    for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
        text = arg.arg
        if default is not None:
            text += f"={ast.unparse(default)}"
        parts.append(text)
    if node.args.kwarg:
        parts.append(f"**{node.args.kwarg.arg}")
    return ", ".join(parts)


def ast_sha(node: ast.AST) -> str:
    normalized = ast.dump(node, annotate_fields=True, include_attributes=False)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def is_main_guard(node: ast.AST) -> bool:
    if not isinstance(node, ast.If):
        return False
    return any(
        isinstance(child, ast.Call)
        and isinstance(child.func, ast.Name)
        and child.func.id == "main"
        for child in ast.walk(node)
    )


def main() -> None:
    app_source = APP_PATH.read_text(encoding="utf-8")
    module_source = MODULE_PATH.read_text(encoding="utf-8")
    app_tree = ast.parse(app_source, filename=str(APP_PATH))
    module_tree = ast.parse(module_source, filename=str(MODULE_PATH))

    app_class = next(node for node in app_tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    legacy = [
        node for node in app_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == TARGET
    ]
    assert not legacy, "Legacy App.open_areas_manager must be removed"

    bindings: list[ast.Assign] = []
    for node in app_tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "App"
                and target.attr == TARGET
            ):
                bindings.append(node)
    assert len(bindings) == 1, f"Expected one active binding, found {len(bindings)}"
    assert ast.unparse(bindings[0].value) == EXPECTED_BINDING_VALUE
    assert "from spina_app.area_hierarchy_ui import open_area_manager as _spina_area_open_manager" in app_source

    final_guards = [node for node in app_tree.body if is_main_guard(node)]
    assert final_guards, "Final main guard not found"
    assert bindings[0].lineno < max(final_guards, key=lambda node: node.lineno).lineno

    app_method_calls = [
        node for node in ast.walk(app_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == TARGET
    ]
    assert not app_method_calls, f"Unexpected App method calls: {len(app_method_calls)}"

    modern_matches = [
        node for node in module_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "open_area_manager"
    ]
    assert len(modern_matches) == 1, f"Expected one modern manager, found {len(modern_matches)}"
    modern = modern_matches[0]
    assert signature(modern) == EXPECTED_MODERN_SIGNATURE
    assert (modern.end_lineno or modern.lineno) - modern.lineno + 1 == EXPECTED_MODERN_LINES
    assert ast_sha(modern) == EXPECTED_MODERN_AST_SHA256

    modern_calls = [
        node for node in ast.walk(module_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "open_area_manager"
    ]
    assert len(modern_calls) == 2, f"Expected two modern selector calls, found {len(modern_calls)}"

    print("Wave 71 legacy area manager cleanup regression passed")


if __name__ == "__main__":
    main()
