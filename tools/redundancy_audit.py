#!/usr/bin/env python3
"""Read-only redundancy audit for a Python source file."""

from __future__ import annotations

import argparse
import ast
import collections
import hashlib
import json
from pathlib import Path

PATCH_CLASSES = {
    "App", "LoanDB", "ClientsTab", "DataBankTab", "ReportsTab",
    "CollectorRouteTab",
}


def body_hash(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    clone = ast.FunctionDef(
        name="_",
        args=node.args,
        body=node.body,
        decorator_list=[],
        returns=node.returns,
        type_comment=getattr(node, "type_comment", None),
    )
    return hashlib.sha256(
        ast.dump(clone, include_attributes=False).encode("utf-8")
    ).hexdigest()


def audit(path: Path) -> dict[str, object]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))

    functions: dict[str, list[ast.AST]] = collections.defaultdict(list)
    classes: dict[str, ast.ClassDef] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions[node.name].append(node)
        elif isinstance(node, ast.ClassDef):
            classes[node.name] = node

    duplicate_functions = {
        name: [node.lineno for node in nodes]
        for name, nodes in sorted(functions.items())
        if len(nodes) > 1
    }

    duplicate_methods: dict[str, dict[str, list[int]]] = {}
    for class_name, class_node in sorted(classes.items()):
        methods: dict[str, list[ast.AST]] = collections.defaultdict(list)
        for node in class_node.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods[node.name].append(node)
        repeated = {
            name: [node.lineno for node in nodes]
            for name, nodes in sorted(methods.items())
            if len(nodes) > 1
        }
        if repeated:
            duplicate_methods[class_name] = repeated

    assignments: dict[str, list[int]] = collections.defaultdict(list)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if not isinstance(target, ast.Attribute):
                continue
            if not isinstance(target.value, ast.Name):
                continue
            if target.value.id not in PATCH_CLASSES:
                continue
            assignments[f"{target.value.id}.{target.attr}"].append(node.lineno)
    repeated_patches = {
        name: lines for name, lines in sorted(assignments.items()) if len(lines) > 1
    }

    hashes: dict[str, list[dict[str, object]]] = collections.defaultdict(list)
    for name, nodes in functions.items():
        for node in nodes:
            hashes[body_hash(node)].append({
                "name": name,
                "line": node.lineno,
                "end_line": node.end_lineno,
            })
    duplicate_bodies = [
        group for group in hashes.values()
        if len(group) > 1 and len({item["name"] for item in group}) > 1
    ]
    duplicate_bodies.sort(key=lambda group: int(group[0]["line"]))

    return {
        "file": path.name,
        "line_count": source.count("\n") + 1,
        "function_definitions": sum(len(nodes) for nodes in functions.values()),
        "unique_function_names": len(functions),
        "duplicate_top_level_definitions": duplicate_functions,
        "duplicate_class_methods": duplicate_methods,
        "repeated_monkey_patch_assignments": repeated_patches,
        "exact_duplicate_top_level_bodies": duplicate_bodies,
    }


def print_report(report: dict[str, object]) -> None:
    print(f"Redundancy audit: {report['file']}")
    print(f"Lines: {report['line_count']}")
    print(
        "Top-level functions: "
        f"{report['function_definitions']} definitions / "
        f"{report['unique_function_names']} unique names"
    )
    for heading, key in (
        ("Duplicate top-level definitions", "duplicate_top_level_definitions"),
        ("Duplicate methods inside classes", "duplicate_class_methods"),
        ("Repeated monkey-patch targets", "repeated_monkey_patch_assignments"),
        ("Exact duplicate helper bodies", "exact_duplicate_top_level_bodies"),
    ):
        print(f"\n{heading}:")
        value = report[key]
        if not value:
            print("  - none")
        elif isinstance(value, dict):
            for name, lines in value.items():
                if isinstance(lines, dict):
                    for method, method_lines in lines.items():
                        print(f"  - {name}.{method}: {method_lines}")
                else:
                    print(f"  - {name}: {lines}")
        else:
            for group in value:
                print("  - " + ", ".join(
                    f"{item['name']}@{item['line']}" for item in group
                ))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("python_file", type=Path)
    parser.add_argument("--json", dest="json_path", type=Path)
    args = parser.parse_args()
    report = audit(args.python_file)
    print_report(report)
    if args.json_path:
        args.json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
