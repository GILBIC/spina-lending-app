#!/usr/bin/env python3
"""Guarded extraction of two date display helpers into ``spina_app.utilities.dates``.

Dry-run by default. Pass ``--apply`` to append the exact function bodies to the
existing dates utility and replace their original top-level definitions with
same-name imports.
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
MODULE_RELATIVE_PATH = Path("spina_app") / "utilities" / "dates.py"
TARGETS = (
    "_spina_dash__date_text",
    "_spina_v24_cilog_parse_day",
)
IMPORT_LINES = {
    name: f"from spina_app.utilities.dates import {name}" for name in TARGETS
}
ALLOWED_EXTERNAL_NAMES = {"datetime", "_spina_dash__parse_date"}


def _line_source(source: str, node: ast.AST) -> str:
    lines = source.splitlines(keepends=True)
    start = int(getattr(node, "lineno")) - 1
    end = int(getattr(node, "end_lineno", getattr(node, "lineno")))
    text = "".join(lines[start:end])
    return text if text.endswith("\n") else text + "\n"


def _top_level_functions(tree: ast.Module, names: set[str]) -> dict[str, ast.FunctionDef]:
    found: dict[str, ast.FunctionDef] = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
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
        elif isinstance(child, ast.ExceptHandler) and isinstance(child.name, str):
            names.add(child.name)
    return names


def _external_loaded_names(node: ast.FunctionDef) -> set[str]:
    loaded = {
        child.id
        for child in ast.walk(node)
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)
    }
    safe = set(dir(builtins)) | _local_names(node) | set(TARGETS)
    return loaded - safe


def _validate_signature(name: str, node: ast.FunctionDef) -> None:
    positional = list(node.args.posonlyargs) + list(node.args.args)
    if len(positional) != 1 or node.args.vararg or node.args.kwarg or node.args.kwonlyargs:
        raise RuntimeError(f"Refusing extraction because {name} no longer has one simple argument.")


def _validate_existing_module(module_source: str) -> ast.Module:
    tree = ast.parse(module_source)
    definitions = _top_level_functions(tree, {"_spina_dash__parse_date"} | set(TARGETS))
    if "_spina_dash__parse_date" not in definitions:
        raise RuntimeError("dates.py must contain _spina_dash__parse_date before this extraction.")
    if any(name in definitions for name in TARGETS):
        present = sorted(name for name in TARGETS if name in definitions)
        raise RuntimeError(f"dates.py already contains unexpected target definitions: {present}.")
    bound_datetime = False
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "datetime":
            if any((alias.asname or alias.name) == "datetime" for alias in node.names):
                bound_datetime = True
        elif isinstance(node, ast.Import):
            if any((alias.asname or alias.name.split('.', 1)[0]) == "datetime" for alias in node.names):
                bound_datetime = True
    if not bound_datetime:
        raise RuntimeError("dates.py must bind datetime before this extraction.")
    return tree


def _append_module_source(module_source: str, app_source: str, functions: dict[str, ast.FunctionDef]) -> str:
    text = module_source.rstrip() + "\n\n"
    for index, name in enumerate(TARGETS):
        text += _line_source(app_source, functions[name]).lstrip()
        if index != len(TARGETS) - 1:
            text += "\n"
    return text.rstrip() + "\n"


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
    functions = _top_level_functions(tree, set(TARGETS))
    imports_present = {name for name, line in IMPORT_LINES.items() if line in source}
    if len(functions) == len(TARGETS) and not imports_present:
        return "original", functions
    if not functions and imports_present == set(TARGETS):
        return "applied", functions
    raise RuntimeError(
        "Refusing mixed date-display extraction state: "
        f"definitions={sorted(functions)}, imports={sorted(imports_present)}."
    )


def build_plan(app_path: Path, package_root: Path) -> dict[str, Any]:
    app_source = app_path.read_text(encoding="utf-8", errors="strict")
    app_tree = ast.parse(app_source)
    state, functions = _state(app_source, app_tree)
    module_path = package_root / MODULE_RELATIVE_PATH
    if not module_path.exists():
        raise RuntimeError("Existing dates.py module is missing.")
    module_source = module_path.read_text(encoding="utf-8", errors="strict")

    if state == "applied":
        module_tree = ast.parse(module_source)
        module_functions = _top_level_functions(module_tree, set(TARGETS))
        if set(module_functions) != set(TARGETS):
            raise RuntimeError("App imports date-display helpers but dates.py does not define both.")
        compile(app_source, str(app_path), "exec")
        compile(module_source, str(module_path), "exec")
        return {
            "already_applied": True,
            "safe_to_apply": True,
            "app_file": str(app_path),
            "module_file": str(module_path),
            "targets": list(TARGETS),
        }

    _validate_existing_module(module_source)
    external_by_target: dict[str, list[str]] = {}
    for name in TARGETS:
        node = functions[name]
        if node.decorator_list:
            raise RuntimeError(f"Refusing extraction because {name} has decorators.")
        if any(isinstance(child, (ast.Global, ast.Nonlocal)) for child in ast.walk(node)):
            raise RuntimeError(f"Refusing extraction because {name} uses global/nonlocal state.")
        _validate_signature(name, node)
        external = _external_loaded_names(node)
        unexpected = external - ALLOWED_EXTERNAL_NAMES
        if unexpected:
            raise RuntimeError(
                f"Refusing extraction because {name} depends on unexpected names: "
                + ", ".join(sorted(unexpected))
            )
        external_by_target[name] = sorted(external)

    module_text = _append_module_source(module_source, app_source, functions)
    patched_text = _patched_source(app_source, functions)
    compile(module_text, str(module_path), "exec")
    compile(patched_text, str(app_path), "exec")

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
        "_legacy_source": "\n".join(
            _line_source(app_source, functions[name]).rstrip() for name in TARGETS
        ) + "\n",
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
    plan.pop("_legacy_source", None)
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
