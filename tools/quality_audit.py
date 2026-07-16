#!/usr/bin/env python3
"""Static code-quality audit for the SPINA single-file application."""
from __future__ import annotations

import argparse
import ast
import json
from collections import Counter
from pathlib import Path


def dotted_name(node: ast.AST) -> str:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def function_metrics(node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict:
    branch_types = (
        ast.If,
        ast.For,
        ast.AsyncFor,
        ast.While,
        ast.Try,
        ast.With,
        ast.AsyncWith,
        ast.Match,
        ast.BoolOp,
        ast.comprehension,
    )
    branches = sum(isinstance(child, branch_types) for child in ast.walk(node))
    return {
        "name": node.name,
        "line": node.lineno,
        "end_line": node.end_lineno,
        "lines": node.end_lineno - node.lineno + 1,
        "branch_nodes": branches,
    }


def module_calls(node: ast.AST):
    """Yield calls executed at module load, skipping function/class bodies."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
        return
    if isinstance(node, ast.Call):
        yield node
    for child in ast.iter_child_nodes(node):
        yield from module_calls(child)


def audit(path: Path) -> dict:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    counts = Counter()
    large_functions = []
    critical_patterns = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
                counts["bare_except"] += 1
            elif isinstance(node.type, ast.Name) and node.type.id == "Exception":
                counts["broad_except"] += 1
            if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                counts["swallowed_except"] += 1
            for child in ast.walk(ast.Module(body=node.body, type_ignores=[])):
                if isinstance(child, ast.Call) and dotted_name(child.func) == "work_fn":
                    critical_patterns.append(
                        {"kind": "task_recalled_in_exception", "line": child.lineno}
                    )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            metric = function_metrics(node)
            if metric["lines"] >= 250 or metric["branch_nodes"] >= 80:
                large_functions.append(metric)
        elif isinstance(node, ast.Call):
            name = dotted_name(node.func)
            if name.endswith(".fetchall"):
                counts["fetchall_calls"] += 1
            if name.endswith(".commit"):
                counts["commit_calls"] += 1
            if name in ("psycopg.connect", "sqlite3.connect"):
                counts["connection_calls"] += 1
            if name.endswith("load_workbook"):
                counts["excel_load_calls"] += 1

    for node in tree.body:
        for call in module_calls(node):
            if dotted_name(call.func) == "LoanDB":
                critical_patterns.append(
                    {"kind": "module_scope_loan_db", "line": call.lineno}
                )

    default_passwords = {"admin123", "encoder123", "viewer123", "system123"}
    password_literals = [
        {"value": node.value, "line": node.lineno}
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value in default_passwords
    ]

    large_functions.sort(
        key=lambda item: (item["lines"], item["branch_nodes"]), reverse=True
    )
    return {
        "file": path.name,
        "line_count": source.count("\n") + 1,
        "counts": dict(counts),
        "critical_patterns": critical_patterns,
        "hardcoded_default_password_literals": password_literals,
        "largest_or_most_complex_functions": large_functions[:25],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("python_file", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--fail-critical", action="store_true")
    args = parser.parse_args()

    report = audit(args.python_file)
    print(json.dumps(report, indent=2))
    if args.json:
        args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 1 if args.fail_critical and report["critical_patterns"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
