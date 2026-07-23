#!/usr/bin/env python3
"""Guarded extraction for the pure CILOG record-difference helper."""

from __future__ import annotations

import argparse
import ast
import builtins
import json
import os
import tempfile
from pathlib import Path

APP_PATH = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
MODULE_PATH = Path("spina_app/utilities/diffs.py")
TARGET = "_spina_cilog_diff_pairs"
IMPORT_LINE = f"from spina_app.utilities.diffs import {TARGET}"
EXPECTED_SIGNATURE = "old_obj, new_obj"


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _function_matches(source: str):
    tree = ast.parse(source)
    matches = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == TARGET
    ]
    return tree, matches


def _local_names(node: ast.FunctionDef) -> set[str]:
    names = {
        arg.arg
        for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
    }
    if node.args.vararg:
        names.add(node.args.vararg.arg)
    if node.args.kwarg:
        names.add(node.args.kwarg.arg)
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and isinstance(child.ctx, (ast.Store, ast.Del)):
            names.add(child.id)
        elif isinstance(child, ast.ExceptHandler) and isinstance(child.name, str):
            names.add(child.name)
    return names


def _validate_node(node: ast.FunctionDef) -> dict[str, object]:
    if node.decorator_list:
        raise RuntimeError("Refusing decorated helper")
    if any(isinstance(child, (ast.Global, ast.Nonlocal)) for child in ast.walk(node)):
        raise RuntimeError("Refusing helper with global/nonlocal state")

    signature = ast.unparse(node.args)
    if signature != EXPECTED_SIGNATURE:
        raise RuntimeError(f"Unexpected signature: {signature!r}")

    loaded = {
        child.id
        for child in ast.walk(node)
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)
    }
    external = sorted(loaded - set(dir(builtins)) - _local_names(node) - {TARGET})
    if external:
        raise RuntimeError(f"Unexpected external dependencies: {external}")

    return {
        "signature": signature,
        "line": node.lineno,
        "end_line": node.end_lineno,
        "external_loaded_names": external,
    }


def _caller_summary(tree: ast.Module) -> list[dict[str, object]]:
    callers = []
    for owner in tree.body:
        if not isinstance(owner, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        count = sum(
            1
            for child in ast.walk(owner)
            if isinstance(child, ast.Call)
            and isinstance(child.func, ast.Name)
            and child.func.id == TARGET
        )
        if count:
            callers.append({
                "name": owner.name,
                "line": owner.lineno,
                "kind": type(owner).__name__,
                "call_count": count,
            })
    return callers


def inspect_state() -> dict[str, object]:
    app_source = APP_PATH.read_text(encoding="utf-8")
    app_tree, app_matches = _function_matches(app_source)
    imported = IMPORT_LINE in app_source

    module_source = MODULE_PATH.read_text(encoding="utf-8") if MODULE_PATH.exists() else ""
    _module_tree, module_matches = _function_matches(module_source) if module_source else (ast.Module(body=[], type_ignores=[]), [])

    state = {
        "target": TARGET,
        "import_present": imported,
        "app_definitions": len(app_matches),
        "module_definitions": len(module_matches),
        "callers": _caller_summary(app_tree),
    }

    if len(app_matches) == 1 and not imported and not module_matches:
        state["mode"] = "ready"
        state["helper"] = _validate_node(app_matches[0])
        return state

    if not app_matches and imported and len(module_matches) == 1:
        state["mode"] = "applied"
        state["helper"] = _validate_node(module_matches[0])
        return state

    state["mode"] = "mixed"
    return state


def apply_extraction() -> dict[str, object]:
    app_source = APP_PATH.read_text(encoding="utf-8")
    app_tree, app_matches = _function_matches(app_source)
    imported = IMPORT_LINE in app_source

    module_source = MODULE_PATH.read_text(encoding="utf-8") if MODULE_PATH.exists() else ""
    _module_tree, module_matches = _function_matches(module_source) if module_source else (ast.Module(body=[], type_ignores=[]), [])

    if not app_matches and imported and len(module_matches) == 1:
        _validate_node(module_matches[0])
        compile(app_source, str(APP_PATH), "exec")
        compile(module_source, str(MODULE_PATH), "exec")
        return {"target": TARGET, "mode": "already_applied"}

    if len(app_matches) != 1 or imported or module_matches:
        raise RuntimeError(
            "Refusing mixed state: "
            f"app_defs={len(app_matches)}, import={imported}, module_defs={len(module_matches)}"
        )

    node = app_matches[0]
    helper_info = _validate_node(node)
    source_lines = app_source.splitlines(keepends=True)
    function_text = "".join(source_lines[node.lineno - 1:node.end_lineno])
    if not function_text.endswith("\n"):
        function_text += "\n"

    source_lines[node.lineno - 1:node.end_lineno] = [IMPORT_LINE + "\n"]
    patched_app = "".join(source_lines)
    patched_module = (
        '"""Pure record-difference helpers extracted from SPINA."""\n\n'
        "from __future__ import annotations\n\n"
        + function_text.lstrip().rstrip()
        + "\n"
    )

    compile(patched_app, str(APP_PATH), "exec")
    compile(patched_module, str(MODULE_PATH), "exec")
    _atomic_write(APP_PATH, patched_app)
    _atomic_write(MODULE_PATH, patched_module)

    return {
        "target": TARGET,
        "mode": "applied",
        "helper": helper_info,
        "callers": _caller_summary(app_tree),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    result = apply_extraction() if args.apply else inspect_state()
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text, encoding="utf-8")
    else:
        print(text, end="")

    if not args.apply and result.get("mode") not in {"ready", "applied"}:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
