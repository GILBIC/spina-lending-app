from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE_PATH = ROOT / "spina_app" / "client_new_status.py"
EXPECTED_AST_SHA256 = "8126404f3be36835e43194271e130c4e3477512e2871e5fa5b313753fd4629c1"
EXPECTED_SIGNATURE = "self, name, ledger_date, days=None"
SELECT_SQL = "SELECT new_until, created_at, date_released FROM clients WHERE name=? AND loan_type=?"
SQL_WRITE_RE = re.compile(r"\b(INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|TRUNCATE|REPLACE)\b", re.I)


def signature(node: ast.FunctionDef) -> str:
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


def is_final_main_guard(node: ast.AST) -> bool:
    if not isinstance(node, ast.If):
        return False
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name) and child.func.id == "main":
            return True
    return False


def main() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    module_text = MODULE_PATH.read_text(encoding="utf-8")
    app_tree = ast.parse(app_text, filename=str(APP_PATH))
    module_tree = ast.parse(module_text, filename=str(MODULE_PATH))

    app_class = next(node for node in app_tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    legacy = [node for node in app_class.body if isinstance(node, ast.FunctionDef) and node.name == "_is_client_new"]
    assert not legacy, "Legacy App._is_client_new must be removed"

    module_matches = [
        node for node in module_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_is_client_new"
    ]
    assert len(module_matches) == 1, f"Expected one module function, found {len(module_matches)}"
    function = module_matches[0]
    assert signature(function) == EXPECTED_SIGNATURE
    normalized = ast.dump(function, annotate_fields=True, include_attributes=False)
    assert hashlib.sha256(normalized.encode("utf-8")).hexdigest() == EXPECTED_AST_SHA256

    string_literals = [
        child.value for child in ast.walk(function)
        if isinstance(child, ast.Constant) and isinstance(child.value, str)
    ]
    assert SELECT_SQL in string_literals
    assert not any(SQL_WRITE_RE.search(value) for value in string_literals)

    callers = [
        child for child in ast.walk(app_tree)
        if isinstance(child, ast.Call)
        and isinstance(child.func, ast.Attribute)
        and child.func.attr == "_is_client_new"
    ]
    assert len(callers) == 4, f"Expected four live callers, found {len(callers)}"

    bindings = []
    for child in ast.walk(app_tree):
        if not isinstance(child, ast.Assign):
            continue
        for target in child.targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "App"
                and target.attr == "_is_client_new"
            ):
                bindings.append(child)
    assert len(bindings) == 1, f"Expected one App binding, found {len(bindings)}"

    final_guards = [node for node in app_tree.body if is_final_main_guard(node)]
    assert final_guards, "Final main guard not found"
    final_guard = max(final_guards, key=lambda node: node.lineno)
    assert bindings[0].lineno < final_guard.lineno

    assert "configure_client_new_status_dependencies as _configure_wave70_client_new" in app_text
    assert "_configure_wave70_client_new(globals())" in app_text
    assert "App._is_client_new = _wave70_is_client_new" in app_text

    print("Wave 70 client-new structural regression passed")


if __name__ == "__main__":
    main()
