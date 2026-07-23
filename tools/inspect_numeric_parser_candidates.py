#!/usr/bin/env python3
"""Write an AST inspection report for proposed numeric-parser extractions."""

from __future__ import annotations

import ast
import builtins
import json
from pathlib import Path

APP_FILE = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
REPORT = Path("tools/fixtures/numeric_parser_inspection.json")
TARGETS = ("_spina_dash__float", "_spina_v27_count_from_text")


def local_names(node: ast.FunctionDef) -> set[str]:
    names = {
        arg.arg
        for arg in (
            list(node.args.posonlyargs)
            + list(node.args.args)
            + list(node.args.kwonlyargs)
        )
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


def main() -> int:
    source = APP_FILE.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source)
    found = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in TARGETS
    }
    report = {"targets": {}}
    for name in TARGETS:
        node = found.get(name)
        if node is None:
            report["targets"][name] = {"found": False}
            continue
        loaded = {
            child.id
            for child in ast.walk(node)
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)
        }
        external = sorted(loaded - set(dir(builtins)) - local_names(node) - set(TARGETS))
        report["targets"][name] = {
            "found": True,
            "line": node.lineno,
            "end_line": node.end_lineno,
            "signature": ast.unparse(node.args),
            "decorators": [ast.unparse(item) for item in node.decorator_list],
            "uses_global_or_nonlocal": any(
                isinstance(child, (ast.Global, ast.Nonlocal)) for child in ast.walk(node)
            ),
            "external_loaded_names": external,
            "source": "\n".join(lines[node.lineno - 1 : node.end_lineno]),
        }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
