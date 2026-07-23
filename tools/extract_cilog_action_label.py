#!/usr/bin/env python3
"""Guarded extraction for the Client Information Log action-label helper."""

from __future__ import annotations

import argparse
import ast
import builtins
import json
import os
import tempfile
from pathlib import Path

APP_FILE = "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
TARGET = "_spina_cilog_action_label"
MODULE = Path("spina_app/utilities/text.py")
IMPORT_LINE = f"from spina_app.utilities.text import {TARGET}"


def _local_names(node: ast.FunctionDef) -> set[str]:
    names = {arg.arg for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)}
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


def _find(tree: ast.Module, name: str) -> list[ast.FunctionDef]:
    return [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name]


def _function_text(source: str, node: ast.FunctionDef) -> str:
    lines = source.splitlines(keepends=True)
    text = "".join(lines[node.lineno - 1 : node.end_lineno])
    return text if text.endswith("\n") else text + "\n"


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


def build_plan(app_path: Path, root: Path) -> dict[str, object]:
    source = app_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    matches = _find(tree, TARGET)
    imported = IMPORT_LINE in source

    module_path = root / MODULE
    module_source = module_path.read_text(encoding="utf-8")
    module_tree = ast.parse(module_source)
    module_matches = _find(module_tree, TARGET)

    if not matches and imported:
        if len(module_matches) != 1:
            raise RuntimeError("Applied state has a missing or duplicate utility helper")
        compile(source, str(app_path), "exec")
        compile(module_source, str(module_path), "exec")
        return {"target": TARGET, "safe_to_apply": True, "already_applied": True}

    if len(matches) != 1 or imported or module_matches:
        raise RuntimeError(
            f"Refusing mixed state: definitions={len(matches)}, import={imported}, module_defs={len(module_matches)}"
        )

    node = matches[0]
    if node.decorator_list:
        raise RuntimeError("Refusing decorated helper")
    if any(isinstance(child, (ast.Global, ast.Nonlocal)) for child in ast.walk(node)):
        raise RuntimeError("Refusing helper with global/nonlocal state")

    loaded = {
        child.id
        for child in ast.walk(node)
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)
    }
    external = loaded - set(dir(builtins)) - _local_names(node) - {TARGET}
    if external:
        raise RuntimeError(f"Unexpected helper dependencies: {sorted(external)}")

    lines = source.splitlines(keepends=True)
    function_text = _function_text(source, node)
    lines[node.lineno - 1 : node.end_lineno] = [IMPORT_LINE + "\n"]
    patched_source = "".join(lines)
    patched_module = module_source.rstrip() + "\n\n" + function_text.lstrip().rstrip() + "\n"

    compile(patched_source, str(app_path), "exec")
    compile(patched_module, str(module_path), "exec")

    return {
        "target": TARGET,
        "safe_to_apply": True,
        "already_applied": False,
        "line": node.lineno,
        "end_line": node.end_lineno,
        "_patched_source": patched_source,
        "_patched_module": patched_module,
    }


def apply(app_path: Path, root: Path) -> dict[str, object]:
    plan = build_plan(app_path, root)
    if plan["already_applied"]:
        return plan
    patched_source = str(plan.pop("_patched_source"))
    patched_module = str(plan.pop("_patched_module"))
    _atomic_write(app_path, patched_source)
    _atomic_write(root / MODULE, patched_module)
    plan["applied"] = True
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", default=APP_FILE)
    parser.add_argument("--root", default=".")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json", dest="json_path")
    args = parser.parse_args()

    app_path = Path(args.file)
    root = Path(args.root)
    result = apply(app_path, root) if args.apply else build_plan(app_path, root)
    public = {key: value for key, value in result.items() if not key.startswith("_")}
    payload = json.dumps(public, indent=2)
    if args.json_path:
        Path(args.json_path).write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
