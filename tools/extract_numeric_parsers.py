#!/usr/bin/env python3
"""Guarded extraction of pure numeric parsers into ``spina_app.utilities.numbers``.

Dry-run by default. Pass ``--apply`` to copy the exact function bodies and
replace their original top-level definitions with same-name imports.
"""

from __future__ import annotations

import argparse
import ast
import builtins
import json
import os
import tempfile
from pathlib import Path
from typing import Any

DEFAULT_APP = "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE_RELATIVE_PATH = Path("spina_app") / "utilities" / "numbers.py"
TARGETS = (
    "_spina_dash__float",
    "_spina_v27_count_from_text",
)
IMPORT_LINES = {
    name: f"from spina_app.utilities.numbers import {name}" for name in TARGETS
}


def _line_source(source: str, node: ast.AST) -> str:
    lines = source.splitlines(keepends=True)
    start = int(getattr(node, "lineno")) - 1
    end = int(getattr(node, "end_lineno", getattr(node, "lineno")))
    text = "".join(lines[start:end])
    return text if text.endswith("\n") else text + "\n"


def _top_level_functions(tree: ast.Module) -> dict[str, ast.FunctionDef]:
    found: dict[str, ast.FunctionDef] = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in TARGETS:
            if node.name in found:
                raise RuntimeError(f"Duplicate top-level definition for {node.name}.")
            found[node.name] = node
    return found


def _local_names(node: ast.FunctionDef) -> set[str]:
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
        elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and child is not node:
            names.add(child.name)
        elif isinstance(child, ast.ExceptHandler) and isinstance(child.name, str):
            names.add(child.name)
    return names


def _external_loaded_names(node: ast.FunctionDef) -> list[str]:
    loaded = {
        child.id
        for child in ast.walk(node)
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)
    }
    safe = set(dir(builtins)) | _local_names(node) | set(TARGETS)
    return sorted(loaded - safe)


def _validate_function(name: str, node: ast.FunctionDef) -> list[str]:
    if node.decorator_list:
        raise RuntimeError(f"Refusing extraction because {name} has decorators.")
    if any(isinstance(child, (ast.Global, ast.Nonlocal)) for child in ast.walk(node)):
        raise RuntimeError(f"Refusing extraction because {name} uses global/nonlocal state.")
    external = _external_loaded_names(node)
    if external:
        raise RuntimeError(
            f"Refusing extraction because {name} depends on external names: "
            + ", ".join(external)
        )
    return external


def _module_source(source: str, functions: dict[str, ast.FunctionDef]) -> str:
    parts = [
        '"""Pure numeric parsing helpers extracted from SPINA."""\n\n',
        "from __future__ import annotations\n\n",
    ]
    for name in TARGETS:
        parts.append(_line_source(source, functions[name]).lstrip())
        parts.append("\n")
    return "".join(parts).rstrip() + "\n"


def _patched_source(source: str, functions: dict[str, ast.FunctionDef]) -> str:
    lines = source.splitlines(keepends=True)
    replacements = sorted(
        ((int(node.lineno) - 1, int(node.end_lineno), name) for name, node in functions.items()),
        reverse=True,
    )
    for start, end, name in replacements:
        lines[start:end] = [IMPORT_LINES[name] + "\n"]
    return "".join(lines)


def _state(source: str, tree: ast.Module) -> tuple[str, dict[str, ast.FunctionDef]]:
    functions = _top_level_functions(tree)
    imports_present = {name for name, line in IMPORT_LINES.items() if line in source}
    if len(functions) == len(TARGETS) and not imports_present:
        return "original", functions
    if not functions and imports_present == set(TARGETS):
        return "applied", functions
    raise RuntimeError(
        "Refusing mixed numeric-parser extraction state: "
        f"definitions={sorted(functions)}, imports={sorted(imports_present)}."
    )


def build_plan(app_path: Path, package_root: Path) -> dict[str, Any]:
    source = app_path.read_text(encoding="utf-8", errors="strict")
    tree = ast.parse(source)
    state, functions = _state(source, tree)
    module_path = package_root / MODULE_RELATIVE_PATH

    if state == "applied":
        if not module_path.exists():
            raise RuntimeError("Numeric parsers are imported but numbers.py is missing.")
        compile(source, str(app_path), "exec")
        compile(module_path.read_text(encoding="utf-8"), str(module_path), "exec")
        return {
            "already_applied": True,
            "safe_to_apply": True,
            "app_file": str(app_path),
            "module_file": str(module_path),
            "targets": list(TARGETS),
        }

    external_by_target = {
        name: _validate_function(name, functions[name]) for name in TARGETS
    }
    module_text = _module_source(source, functions)
    patched_text = _patched_source(source, functions)
    compile(module_text, str(module_path), "exec")
    compile(patched_text, str(app_path), "exec")

    if module_path.exists():
        raise RuntimeError("Refusing to overwrite an existing numbers.py module.")

    return {
        "already_applied": False,
        "safe_to_apply": True,
        "app_file": str(app_path),
        "module_file": str(module_path),
        "targets": [
            {
                "name": name,
                "line": int(functions[name].lineno),
                "end_line": int(functions[name].end_lineno),
                "external_loaded_names": external_by_target[name],
                "replacement": IMPORT_LINES[name],
            }
            for name in TARGETS
        ],
        "_module_text": module_text,
        "_patched_source": patched_text,
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


def apply_extraction(app_path: Path, package_root: Path) -> dict[str, Any]:
    plan = build_plan(app_path, package_root)
    if plan["already_applied"]:
        return plan
    module_text = str(plan.pop("_module_text"))
    patched_source = str(plan.pop("_patched_source"))
    _atomic_write(package_root / MODULE_RELATIVE_PATH, module_text)
    _atomic_write(app_path, patched_source)
    plan["applied"] = True
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", default=DEFAULT_APP)
    parser.add_argument("--package-root", default=".")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json", dest="json_path")
    args = parser.parse_args()

    result = (
        apply_extraction(Path(args.file), Path(args.package_root))
        if args.apply
        else build_plan(Path(args.file), Path(args.package_root))
    )
    public = {key: value for key, value in result.items() if not key.startswith("_")}
    payload = json.dumps(public, indent=2, ensure_ascii=False)
    if args.json_path:
        Path(args.json_path).write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
