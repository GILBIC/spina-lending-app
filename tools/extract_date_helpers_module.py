#!/usr/bin/env python3
"""Guarded extraction of three pure date helpers into ``spina_app.utilities.dates``.

The command is a dry-run unless ``--apply`` is supplied. It copies the exact
function source and only the standard-library import statements required by the
selected functions. It refuses decorators, shared globals, app-level calls,
non-standard-library imports, and partially applied states.
"""

from __future__ import annotations

import argparse
import ast
import builtins
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

DEFAULT_APP = "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE_RELATIVE_PATH = Path("spina_app") / "utilities" / "dates.py"
TARGETS = (
    "_spina_cashctl__valid_date",
    "_spina__parse_day_ymd",
    "_spina_dash__parse_date",
)
IMPORT_LINES = {
    name: f"from spina_app.utilities.dates import {name}" for name in TARGETS
}


def _line_source(source: str, node: ast.AST) -> str:
    lines = source.splitlines(keepends=True)
    start = int(getattr(node, "lineno")) - 1
    end = int(getattr(node, "end_lineno", getattr(node, "lineno")))
    text = "".join(lines[start:end])
    if not text.endswith("\n"):
        text += "\n"
    return text


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


def _external_loaded_names(node: ast.FunctionDef) -> set[str]:
    loaded = {
        child.id
        for child in ast.walk(node)
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)
    }
    safe = set(dir(builtins)) | _local_names(node) | set(TARGETS)
    return loaded - safe


def _import_bindings(node: ast.Import | ast.ImportFrom) -> dict[str, str]:
    bindings: dict[str, str] = {}
    if isinstance(node, ast.Import):
        for alias in node.names:
            bound = alias.asname or alias.name.split(".", 1)[0]
            bindings[bound] = alias.name.split(".", 1)[0]
    else:
        module = str(node.module or "")
        root = module.split(".", 1)[0]
        for alias in node.names:
            if alias.name == "*":
                continue
            bindings[alias.asname or alias.name] = root
    return bindings


def _stdlib_roots() -> set[str]:
    roots = set(getattr(sys, "stdlib_module_names", set()))
    roots.update({"__future__", "datetime", "calendar", "re", "time", "decimal"})
    return roots


def _required_import_nodes(
    tree: ast.Module,
    source: str,
    external_names: set[str],
) -> list[ast.Import | ast.ImportFrom]:
    candidates: dict[str, list[tuple[ast.Import | ast.ImportFrom, str]]] = {
        name: [] for name in external_names
    }
    for node in tree.body:
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        bindings = _import_bindings(node)
        for name in external_names:
            if name in bindings:
                candidates[name].append((node, bindings[name]))

    selected: dict[int, ast.Import | ast.ImportFrom] = {}
    stdlib = _stdlib_roots()
    for name in sorted(external_names):
        matches = candidates.get(name) or []
        if not matches:
            raise RuntimeError(
                f"Refusing extraction because {name!r} is not a local, builtin, target, "
                "or top-level imported name."
            )
        node, root = sorted(matches, key=lambda item: int(item[0].lineno))[0]
        if root not in stdlib:
            raise RuntimeError(
                f"Refusing extraction because {name!r} comes from non-standard-library "
                f"module {root!r}."
            )
        selected[int(node.lineno)] = node

    ordered = [selected[key] for key in sorted(selected)]
    for node in ordered:
        compile(_line_source(source, node), "<date-helper-import>", "exec")
    return ordered


def _module_source(
    source: str,
    functions: dict[str, ast.FunctionDef],
    imports: list[ast.Import | ast.ImportFrom],
) -> str:
    parts = [
        '"""Pure date parsing and validation helpers extracted from SPINA."""\n\n',
        "from __future__ import annotations\n\n",
    ]
    seen_imports: set[str] = set()
    for node in imports:
        text = _line_source(source, node).strip()
        if text and text != "from __future__ import annotations" and text not in seen_imports:
            parts.append(text + "\n")
            seen_imports.add(text)
    if seen_imports:
        parts.append("\n")
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
        "Refusing a mixed or partial date-helper extraction state: "
        f"definitions={sorted(functions)}, imports={sorted(imports_present)}."
    )


def build_plan(app_path: Path, package_root: Path) -> dict[str, Any]:
    source = app_path.read_text(encoding="utf-8", errors="strict")
    tree = ast.parse(source)
    state, functions = _state(source, tree)
    module_path = package_root / MODULE_RELATIVE_PATH

    if state == "applied":
        if not module_path.exists():
            raise RuntimeError("Date helpers are imported but the dates module is missing.")
        compile(module_path.read_text(encoding="utf-8"), str(module_path), "exec")
        compile(source, str(app_path), "exec")
        return {
            "already_applied": True,
            "safe_to_apply": True,
            "app_file": str(app_path),
            "module_file": str(module_path),
            "targets": list(TARGETS),
        }

    external_by_target: dict[str, list[str]] = {}
    all_external: set[str] = set()
    for name in TARGETS:
        node = functions[name]
        if node.decorator_list:
            raise RuntimeError(f"Refusing extraction because {name} has decorators.")
        if any(isinstance(child, (ast.Global, ast.Nonlocal)) for child in ast.walk(node)):
            raise RuntimeError(f"Refusing extraction because {name} uses global/nonlocal state.")
        external = _external_loaded_names(node)
        external_by_target[name] = sorted(external)
        all_external.update(external)

    import_nodes = _required_import_nodes(tree, source, all_external)
    module_text = _module_source(source, functions, import_nodes)
    patched_text = _patched_source(source, functions)
    compile(module_text, str(module_path), "exec")
    compile(patched_text, str(app_path), "exec")

    if module_path.exists() and module_path.read_text(encoding="utf-8") != module_text:
        raise RuntimeError("Refusing to overwrite an existing, different dates.py module.")

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
        "copied_imports": [_line_source(source, node).strip() for node in import_nodes],
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
    _atomic_write(package_root / MODULE_RELATIVE_PATH, module_text)
    _atomic_write(app_path, patched_source)
    plan["applied"] = True
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", default=DEFAULT_APP, help="SPINA app source file")
    parser.add_argument("--package-root", default=".", help="Repository root")
    parser.add_argument("--apply", action="store_true", help="Write the extraction")
    parser.add_argument("--json", dest="json_path", help="Write public result JSON")
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
