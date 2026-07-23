#!/usr/bin/env python3
"""Guarded extraction of one pure JSON helper into SPINA utilities."""

from __future__ import annotations

import argparse
import ast
import builtins
import json
import os
import tempfile
from pathlib import Path

APP_FILE = "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
TARGET = "_spina_cilog_safe_json"
MODULE = Path("spina_app/utilities/serialization.py")
IMPORT_LINE = f"from spina_app.utilities.serialization import {TARGET}"


def _source(source: str, node: ast.AST) -> str:
    lines = source.splitlines(keepends=True)
    text = "".join(lines[node.lineno - 1 : node.end_lineno])
    return text if text.endswith("\n") else text + "\n"


def _function(tree: ast.Module) -> ast.FunctionDef | None:
    matches = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == TARGET]
    if len(matches) > 1:
        raise RuntimeError(f"Duplicate definition for {TARGET}")
    return matches[0] if matches else None


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


def _validate(node: ast.FunctionDef) -> None:
    if node.decorator_list:
        raise RuntimeError("Refusing decorated helper")
    if any(isinstance(child, (ast.Global, ast.Nonlocal)) for child in ast.walk(node)):
        raise RuntimeError("Refusing helper with global/nonlocal state")
    loaded = {
        child.id
        for child in ast.walk(node)
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)
    }
    external = loaded - set(dir(builtins)) - _local_names(node) - {TARGET}
    if external != {"json"}:
        raise RuntimeError(f"Unexpected dependencies: {sorted(external)}")


def build_plan(app_path: Path, root: Path) -> dict[str, object]:
    source = app_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    node = _function(tree)
    imported = IMPORT_LINE in source
    module_path = root / MODULE

    if node is None and imported:
        if not module_path.exists():
            raise RuntimeError("Helper import exists but serialization.py is missing")
        compile(source, str(app_path), "exec")
        compile(module_path.read_text(encoding="utf-8"), str(module_path), "exec")
        return {"already_applied": True, "safe_to_apply": True, "target": TARGET}
    if node is None or imported:
        raise RuntimeError("Refusing mixed extraction state")

    _validate(node)
    function_text = _source(source, node).lstrip()
    module_text = (
        '"""Small serialization helpers extracted from SPINA."""\n\n'
        "from __future__ import annotations\n\n"
        "import json\n\n"
        + function_text.rstrip()
        + "\n"
    )
    lines = source.splitlines(keepends=True)
    lines[node.lineno - 1 : node.end_lineno] = [IMPORT_LINE + "\n"]
    patched = "".join(lines)
    compile(module_text, str(module_path), "exec")
    compile(patched, str(app_path), "exec")
    if module_path.exists():
        raise RuntimeError("Refusing to overwrite existing serialization.py")
    return {
        "already_applied": False,
        "safe_to_apply": True,
        "target": TARGET,
        "line": node.lineno,
        "end_line": node.end_lineno,
        "_module_text": module_text,
        "_patched_source": patched,
    }


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def apply(app_path: Path, root: Path) -> dict[str, object]:
    plan = build_plan(app_path, root)
    if plan["already_applied"]:
        return plan
    module_text = str(plan.pop("_module_text"))
    patched = str(plan.pop("_patched_source"))
    _write(root / MODULE, module_text)
    _write(app_path, patched)
    plan["applied"] = True
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", default=APP_FILE)
    parser.add_argument("--root", default=".")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json", dest="json_path")
    args = parser.parse_args()
    result = apply(Path(args.file), Path(args.root)) if args.apply else build_plan(Path(args.file), Path(args.root))
    public = {key: value for key, value in result.items() if not key.startswith("_")}
    payload = json.dumps(public, indent=2)
    if args.json_path:
        Path(args.json_path).write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
