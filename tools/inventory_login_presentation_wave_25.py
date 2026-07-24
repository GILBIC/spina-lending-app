"""Read-only inventory for SPINA modularization Wave 25 login presentation.

This tool does not modify application code.
"""

from __future__ import annotations

import ast
import builtins
import hashlib
import json
import subprocess
from collections import defaultdict
from pathlib import Path

SOURCE = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
THEME_MODULE = Path("spina_app/theme_palettes.py")
OUTPUT = Path("wave-25-inventory.json")
EXPECTED_BASE = "55d2655e8309e144a9a3b6171c15ce6a4b3da33b"
TARGETS = (
    "_spina_v32_login_colors",
    "_spina_v32_selected_label_for_user",
)
CALLER_NAMES = (
    "_spina_v32_login_button",
    "_spina_v32_prompt_login",
)


def _base_commit() -> str:
    result = subprocess.run(
        ["git", "merge-base", "HEAD", "origin/main"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _source(lines: list[str], node: ast.AST) -> str:
    return "\n".join(lines[node.lineno - 1 : node.end_lineno])


def _called_names(node: ast.AST) -> list[str]:
    calls: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        if isinstance(child.func, ast.Name):
            calls.add(child.func.id)
        elif isinstance(child.func, ast.Attribute):
            calls.add(child.func.attr)
    return sorted(calls)


def _local_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    names = {arg.arg for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs}
    if node.args.vararg:
        names.add(node.args.vararg.arg)
    if node.args.kwarg:
        names.add(node.args.kwarg.arg)
    for child in ast.walk(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and child is not node:
            names.add(child.name)
        elif isinstance(child, ast.Name) and isinstance(child.ctx, (ast.Store, ast.Param)):
            names.add(child.id)
        elif isinstance(child, ast.alias):
            names.add(child.asname or child.name.split(".")[0])
    return names


def _globals(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    local = _local_names(node)
    builtin_names = set(dir(builtins))
    loaded = {
        child.id
        for child in ast.walk(node)
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)
    }
    return sorted(name for name in loaded if name not in local and name not in builtin_names)


def _entry(name: str, node: ast.FunctionDef | ast.AsyncFunctionDef, lines: list[str], callers: dict[str, set[str]]) -> dict[str, object]:
    source = _source(lines, node)
    return {
        "name": name,
        "start_line": node.lineno,
        "end_line": node.end_lineno,
        "lines": node.end_lineno - node.lineno + 1,
        "sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "called_names": _called_names(node),
        "global_dependencies": _globals(node),
        "direct_callers": sorted(callers.get(name, set())),
        "source": source,
    }


def main() -> None:
    base_commit = _base_commit()
    if base_commit != EXPECTED_BASE:
        raise SystemExit(f"Unexpected main base: {base_commit}")

    text = SOURCE.read_text(encoding="utf-8")
    lines = text.splitlines()
    tree = ast.parse(text, filename=str(SOURCE))
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    missing = sorted((set(TARGETS) | set(CALLER_NAMES)) - set(functions))
    if missing:
        raise SystemExit(f"Missing expected login functions: {missing}")

    callers: dict[str, set[str]] = defaultdict(set)
    for caller_name, caller_node in functions.items():
        for called in _called_names(caller_node):
            if called in functions and called != caller_name:
                callers[called].add(caller_name)

    payload = {
        "base_commit": base_commit,
        "source": str(SOURCE),
        "source_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "source_lines": len(lines),
        "theme_module": str(THEME_MODULE),
        "theme_module_sha256": hashlib.sha256(THEME_MODULE.read_bytes()).hexdigest(),
        "targets": [_entry(name, functions[name], lines, callers) for name in TARGETS],
        "protected_callers": [_entry(name, functions[name], lines, callers) for name in CALLER_NAMES],
    }
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    for target in payload["targets"]:
        print(
            f"{target['name']}: lines={target['lines']} "
            f"callers={target['direct_callers']} globals={target['global_dependencies']}"
        )
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
