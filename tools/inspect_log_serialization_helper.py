#!/usr/bin/env python3
"""Inspect the proposed log-serialization helper without changing production code."""

from __future__ import annotations

import ast
import builtins
import json
from pathlib import Path

APP = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
REPORT = Path("tools/fixtures/log_serialization_helper_inspection.json")
TARGET = "_spina_cilog_safe_json"


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


def main() -> int:
    source = APP.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source)
    matches = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == TARGET]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {TARGET} definition, found {len(matches)}")
    node = matches[0]
    loaded = {
        child.id
        for child in ast.walk(node)
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)
    }
    external = sorted(loaded - set(dir(builtins)) - _local_names(node) - {TARGET})
    callers = []
    for owner in tree.body:
        if not isinstance(owner, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if any(
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Name)
            and child.func.id == TARGET
            for child in ast.walk(owner)
        ):
            callers.append({"name": owner.name, "line": owner.lineno, "kind": type(owner).__name__})
    report = {
        "target": TARGET,
        "line": node.lineno,
        "end_line": node.end_lineno,
        "signature": ast.unparse(node.args),
        "decorators": [ast.unparse(item) for item in node.decorator_list],
        "uses_global_or_nonlocal": any(isinstance(child, (ast.Global, ast.Nonlocal)) for child in ast.walk(node)),
        "external_loaded_names": external,
        "source": "\n".join(lines[node.lineno - 1 : node.end_lineno]),
        "callers": callers,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
