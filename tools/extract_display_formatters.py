#!/usr/bin/env python3
"""Guarded extraction of three pure display formatters into formatting.py.

Dry-run by default. Pass --apply to copy the exact function bodies and replace
only their original top-level definitions with same-name imports.
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
MODULE_RELATIVE_PATH = Path("spina_app") / "utilities" / "formatting.py"
TARGETS = (
    "_spina_dash__fmt_pct",
    "_spina_v23_money",
    "_spina_v23_percent",
)
IMPORT_LINES = {
    name: f"from spina_app.utilities.formatting import {name}" for name in TARGETS
}


def _node_source(source: str, node: ast.AST) -> str:
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


def _module_target_counts(module_source: str) -> dict[str, int]:
    tree = ast.parse(module_source)
    return {
        name: sum(
            1
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == name
        )
        for name in TARGETS
    }


def _state(source: str, tree: ast.Module) -> tuple[str, dict[str, ast.FunctionDef]]:
    functions = _top_level_functions(tree)
    imports = {name for name, line in IMPORT_LINES.items() if line in source}
    if set(functions) == set(TARGETS) and not imports:
        return "original", functions
    if not functions and imports == set(TARGETS):
        return "applied", functions
    raise RuntimeError(
        "Refusing mixed display-formatter state: "
        f"definitions={sorted(functions)}, imports={sorted(imports)}."
    )


def _patched_source(source: str, functions: dict[str, ast.FunctionDef]) -> str:
    lines = source.splitlines(keepends=True)
    replacements = sorted(
        (
            (int(node.lineno) - 1, int(node.end_lineno), name)
            for name, node in functions.items()
        ),
        reverse=True,
    )
    for start, end, name in replacements:
        lines[start:end] = [IMPORT_LINES[name] + "\n"]
    return "".join(lines)


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


def build_plan(app_path: Path, package_root: Path) -> dict[str, Any]:
    source = app_path.read_text(encoding="utf-8", errors="strict")
    tree = ast.parse(source)
    state, functions = _state(source, tree)
    module_path = package_root / MODULE_RELATIVE_PATH
    if not module_path.exists():
        raise RuntimeError("Existing formatting.py module is missing.")
    existing_module = module_path.read_text(encoding="utf-8", errors="strict")
    compile(existing_module, str(module_path), "exec")
    counts = _module_target_counts(existing_module)

    if state == "applied":
        if counts != {name: 1 for name in TARGETS}:
            raise RuntimeError(f"Imported formatters are missing or duplicated in formatting.py: {counts}")
        compile(source, str(app_path), "exec")
        return {
            "already_applied": True,
            "safe_to_apply": True,
            "app_file": str(app_path),
            "module_file": str(module_path),
            "targets": list(TARGETS),
        }

    if any(counts.values()):
        raise RuntimeError(f"Refusing to append duplicate formatter definitions: {counts}")

    function_sources: dict[str, str] = {}
    target_details: list[dict[str, Any]] = []
    for name in TARGETS:
        node = functions[name]
        if node.decorator_list:
            raise RuntimeError(f"Refusing extraction because {name} has decorators.")
        if any(isinstance(child, (ast.Global, ast.Nonlocal)) for child in ast.walk(node)):
            raise RuntimeError(f"Refusing extraction because {name} uses global/nonlocal state.")
        external = _external_loaded_names(node)
        if external:
            raise RuntimeError(
                f"Refusing extraction because {name} depends on external names: {external}"
            )
        text = _node_source(source, node).lstrip()
        compile(text, f"<{name}>", "exec")
        function_sources[name] = text
        target_details.append(
            {
                "name": name,
                "line": int(node.lineno),
                "end_line": int(node.end_lineno),
                "external_loaded_names": external,
                "replacement": IMPORT_LINES[name],
            }
        )

    appended = existing_module.rstrip() + "\n\n" + "\n".join(
        function_sources[name].rstrip() for name in TARGETS
    ) + "\n"
    patched = _patched_source(source, functions)
    compile(appended, str(module_path), "exec")
    compile(patched, str(app_path), "exec")
    if _module_target_counts(appended) != {name: 1 for name in TARGETS}:
        raise RuntimeError("Generated formatting module does not contain exactly one of each target.")

    return {
        "already_applied": False,
        "safe_to_apply": True,
        "app_file": str(app_path),
        "module_file": str(module_path),
        "targets": target_details,
        "_function_sources": function_sources,
        "_module_text": appended,
        "_patched_source": patched,
    }


def apply_extraction(app_path: Path, package_root: Path) -> dict[str, Any]:
    plan = build_plan(app_path, package_root)
    if plan["already_applied"]:
        return plan
    module_text = str(plan.pop("_module_text"))
    patched_source = str(plan.pop("_patched_source"))
    plan.pop("_function_sources", None)
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
