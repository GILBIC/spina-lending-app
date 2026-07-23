#!/usr/bin/env python3
"""Guarded extraction of the CILOG value formatter into formatting utilities."""

from __future__ import annotations

import argparse
import ast
import builtins
import json
import os
import tempfile
from pathlib import Path

APP_FILE = "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
TARGET = "_spina_cilog_fmt_value"
DEPENDENCY = "_spina_cilog_fmt_money"
MODULE = Path("spina_app/utilities/formatting.py")
IMPORT_LINE = f"from spina_app.utilities.formatting import {TARGET}"


def _node_source(source: str, node: ast.AST) -> str:
    lines = source.splitlines(keepends=True)
    text = "".join(lines[node.lineno - 1 : node.end_lineno])
    return text if text.endswith("\n") else text + "\n"


def _top_level_function(tree: ast.Module, name: str) -> ast.FunctionDef | None:
    matches = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(matches) > 1:
        raise RuntimeError(f"Duplicate top-level definition for {name}")
    return matches[0] if matches else None


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


def _validate(node: ast.FunctionDef) -> None:
    if node.decorator_list:
        raise RuntimeError("Refusing decorated formatter")
    if any(isinstance(child, (ast.Global, ast.Nonlocal)) for child in ast.walk(node)):
        raise RuntimeError("Refusing formatter with global/nonlocal state")
    loaded = {
        child.id
        for child in ast.walk(node)
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)
    }
    external = loaded - set(dir(builtins)) - _local_names(node) - {TARGET}
    if external != {DEPENDENCY}:
        raise RuntimeError(f"Unexpected formatter dependencies: {sorted(external)}")


def build_plan(app_path: Path, root: Path) -> dict[str, object]:
    source = app_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    node = _top_level_function(tree, TARGET)
    imported = IMPORT_LINE in source

    module_path = root / MODULE
    module_source = module_path.read_text(encoding="utf-8")
    module_tree = ast.parse(module_source)
    module_target = _top_level_function(module_tree, TARGET)
    module_dependency = _top_level_function(module_tree, DEPENDENCY)
    if module_dependency is None:
        raise RuntimeError(f"Required utility dependency {DEPENDENCY} is missing")

    if node is None and imported:
        if module_target is None:
            raise RuntimeError("Formatter import exists but utility definition is missing")
        compile(source, str(app_path), "exec")
        compile(module_source, str(module_path), "exec")
        return {
            "already_applied": True,
            "safe_to_apply": True,
            "target": TARGET,
            "dependency": DEPENDENCY,
        }

    if node is None or imported or module_target is not None:
        raise RuntimeError(
            "Refusing mixed extraction state: "
            f"app_definition={node is not None}, import={imported}, module_definition={module_target is not None}"
        )

    _validate(node)
    function_text = _node_source(source, node).lstrip()
    source_lines = source.splitlines(keepends=True)
    source_lines[node.lineno - 1 : node.end_lineno] = [IMPORT_LINE + "\n"]
    patched_source = "".join(source_lines)
    patched_module = module_source.rstrip() + "\n\n" + function_text.rstrip() + "\n"

    compile(patched_source, str(app_path), "exec")
    compile(patched_module, str(module_path), "exec")

    return {
        "already_applied": False,
        "safe_to_apply": True,
        "target": TARGET,
        "dependency": DEPENDENCY,
        "line": node.lineno,
        "end_line": node.end_lineno,
        "_function_text": function_text,
        "_patched_source": patched_source,
        "_patched_module": patched_module,
    }


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


def apply_extraction(app_path: Path, root: Path) -> dict[str, object]:
    plan = build_plan(app_path, root)
    if plan["already_applied"]:
        return plan
    patched_source = str(plan.pop("_patched_source"))
    patched_module = str(plan.pop("_patched_module"))
    plan.pop("_function_text", None)
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

    result = (
        apply_extraction(Path(args.file), Path(args.root))
        if args.apply
        else build_plan(Path(args.file), Path(args.root))
    )
    public = {key: value for key, value in result.items() if not key.startswith("_")}
    payload = json.dumps(public, indent=2, ensure_ascii=False)
    if args.json_path:
        Path(args.json_path).write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
