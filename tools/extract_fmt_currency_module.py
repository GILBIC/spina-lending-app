#!/usr/bin/env python3
"""Guarded first extraction: move top-level ``fmt_currency`` into a utility module.

The command is dry-run by default. Pass ``--apply`` to write changes.
It preserves the public global name by replacing the original function with:

    from spina_app.utilities.formatting import fmt_currency
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
FUNCTION_NAME = "fmt_currency"
IMPORT_LINE = "from spina_app.utilities.formatting import fmt_currency"
MODULE_RELATIVE_PATH = Path("spina_app") / "utilities" / "formatting.py"


def _find_top_level_function(tree: ast.Module) -> ast.FunctionDef:
    matches = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == FUNCTION_NAME
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one top-level {FUNCTION_NAME} definition; found {len(matches)}."
        )
    return matches[0]


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
    safe = set(dir(builtins)) | _local_names(node) | {FUNCTION_NAME}
    return sorted(loaded - safe)


def _function_source(source: str, node: ast.FunctionDef) -> str:
    lines = source.splitlines(keepends=True)
    start = int(node.lineno) - 1
    end = int(getattr(node, "end_lineno", node.lineno))
    text = "".join(lines[start:end])
    if not text.endswith("\n"):
        text += "\n"
    return text


def _module_source(function_source: str) -> str:
    return (
        '"""Small formatting helpers extracted from the SPINA desktop app."""\n\n'
        "from __future__ import annotations\n\n"
        + function_source.lstrip()
    )


def _replace_definition(source: str, node: ast.FunctionDef) -> str:
    lines = source.splitlines(keepends=True)
    start = int(node.lineno) - 1
    end = int(getattr(node, "end_lineno", node.lineno))
    replacement = IMPORT_LINE + "\n"
    return "".join(lines[:start]) + replacement + "".join(lines[end:])


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def build_plan(app_path: Path, package_root: Path) -> dict[str, Any]:
    source = app_path.read_text(encoding="utf-8", errors="strict")
    if IMPORT_LINE in source and f"def {FUNCTION_NAME}" not in source:
        return {
            "already_applied": True,
            "app_file": str(app_path),
            "module_file": str(package_root / MODULE_RELATIVE_PATH),
            "function": FUNCTION_NAME,
            "safe_to_apply": True,
            "external_loaded_names": [],
        }

    tree = ast.parse(source)
    node = _find_top_level_function(tree)
    external_names = _external_loaded_names(node)
    if node.decorator_list:
        raise RuntimeError("Refusing extraction because fmt_currency has decorators.")
    if external_names:
        raise RuntimeError(
            "Refusing extraction because fmt_currency depends on external names: "
            + ", ".join(external_names)
        )

    function_text = _function_source(source, node)
    compile(function_text, f"<{FUNCTION_NAME}>", "exec")
    module_text = _module_source(function_text)
    patched_source = _replace_definition(source, node)
    compile(module_text, str(package_root / MODULE_RELATIVE_PATH), "exec")
    compile(patched_source, str(app_path), "exec")

    return {
        "already_applied": False,
        "app_file": str(app_path),
        "module_file": str(package_root / MODULE_RELATIVE_PATH),
        "function": FUNCTION_NAME,
        "line": int(node.lineno),
        "end_line": int(getattr(node, "end_lineno", node.lineno)),
        "safe_to_apply": True,
        "external_loaded_names": external_names,
        "_module_text": module_text,
        "_patched_source": patched_source,
    }


def apply_extraction(app_path: Path, package_root: Path) -> dict[str, Any]:
    plan = build_plan(app_path, package_root)
    if plan["already_applied"]:
        return plan

    package_dir = package_root / "spina_app"
    utilities_dir = package_dir / "utilities"
    _atomic_write(
        package_dir / "__init__.py",
        '"""SPINA application package created through small, reviewed extractions."""\n',
    )
    _atomic_write(
        utilities_dir / "__init__.py",
        '"""Reusable SPINA utility modules."""\n',
    )
    _atomic_write(package_root / MODULE_RELATIVE_PATH, str(plan.pop("_module_text")))
    _atomic_write(app_path, str(plan.pop("_patched_source")))
    plan["applied"] = True
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", default=DEFAULT_APP, help="SPINA app source file")
    parser.add_argument(
        "--package-root",
        default=".",
        help="Repository root where the spina_app package will be created",
    )
    parser.add_argument("--apply", action="store_true", help="Write the extraction")
    parser.add_argument("--json", dest="json_path", help="Write the result to JSON")
    args = parser.parse_args()

    app_path = Path(args.file)
    package_root = Path(args.package_root)
    result = (
        apply_extraction(app_path, package_root)
        if args.apply
        else build_plan(app_path, package_root)
    )
    public_result = {key: value for key, value in result.items() if not key.startswith("_")}
    payload = json.dumps(public_result, indent=2, ensure_ascii=False)
    if args.json_path:
        Path(args.json_path).write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
