#!/usr/bin/env python3
"""Guarded extraction for the pure _as_note_dict helper."""

from __future__ import annotations

import argparse
import ast
import builtins
import json
import os
import tempfile
from pathlib import Path

APP_PATH = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
MODULE_PATH = Path("spina_app/utilities/notes.py")
TARGET = "_as_note_dict"
IMPORT_LINE = f"from spina_app.utilities.notes import {TARGET}"
EXPECTED_SIGNATURE = "entry"


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def top_level_functions(source: str) -> list[ast.FunctionDef]:
    tree = ast.parse(source)
    return [node for node in tree.body if isinstance(node, ast.FunctionDef)]


def external_names(node: ast.FunctionDef) -> set[str]:
    local_names = {arg.arg for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)}
    if node.args.vararg:
        local_names.add(node.args.vararg.arg)
    if node.args.kwarg:
        local_names.add(node.args.kwarg.arg)
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and isinstance(child.ctx, (ast.Store, ast.Del)):
            local_names.add(child.id)
        elif isinstance(child, ast.ExceptHandler) and isinstance(child.name, str):
            local_names.add(child.name)
    loaded = {
        child.id
        for child in ast.walk(node)
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)
    }
    return loaded - set(dir(builtins)) - local_names - {TARGET}


def build_plan() -> dict[str, object]:
    app_source = APP_PATH.read_text(encoding="utf-8")
    imported = IMPORT_LINE in app_source
    app_matches = [node for node in top_level_functions(app_source) if node.name == TARGET]

    module_exists = MODULE_PATH.exists()
    module_source = MODULE_PATH.read_text(encoding="utf-8") if module_exists else ""
    module_matches = [node for node in top_level_functions(module_source) if node.name == TARGET] if module_source else []

    state = "unknown"
    if len(app_matches) == 1 and not imported and not module_matches:
        state = "source"
    elif not app_matches and imported and len(module_matches) == 1:
        state = "extracted"

    plan: dict[str, object] = {
        "target": TARGET,
        "state": state,
        "app_definitions": len(app_matches),
        "import_present": imported,
        "module_definitions": len(module_matches),
        "module_exists": module_exists,
    }

    if state == "source":
        node = app_matches[0]
        plan.update(
            {
                "line": node.lineno,
                "end_line": node.end_lineno,
                "signature": ast.unparse(node.args),
                "decorators": [ast.unparse(item) for item in node.decorator_list],
                "uses_global_or_nonlocal": any(
                    isinstance(child, (ast.Global, ast.Nonlocal)) for child in ast.walk(node)
                ),
                "external_names": sorted(external_names(node)),
            }
        )
    return plan


def validate_plan(plan: dict[str, object]) -> None:
    if plan["state"] not in {"source", "extracted"}:
        raise RuntimeError(f"Refusing mixed or unexpected state: {plan}")
    if plan["state"] == "source":
        if plan.get("signature") != EXPECTED_SIGNATURE:
            raise RuntimeError(f"Unexpected signature: {plan.get('signature')!r}")
        if plan.get("decorators"):
            raise RuntimeError("Refusing decorated helper")
        if plan.get("uses_global_or_nonlocal"):
            raise RuntimeError("Refusing helper with global/nonlocal state")
        if plan.get("external_names"):
            raise RuntimeError(f"Unexpected dependencies: {plan.get('external_names')}")


def apply_extraction() -> dict[str, object]:
    plan = build_plan()
    validate_plan(plan)
    if plan["state"] == "extracted":
        compile(APP_PATH.read_text(encoding="utf-8"), str(APP_PATH), "exec")
        compile(MODULE_PATH.read_text(encoding="utf-8"), str(MODULE_PATH), "exec")
        return plan

    app_source = APP_PATH.read_text(encoding="utf-8")
    node = next(node for node in top_level_functions(app_source) if node.name == TARGET)
    source_lines = app_source.splitlines(keepends=True)
    function_text = "".join(source_lines[node.lineno - 1 : node.end_lineno])
    if not function_text.endswith("\n"):
        function_text += "\n"

    source_lines[node.lineno - 1 : node.end_lineno] = [IMPORT_LINE + "\n"]
    patched_app = "".join(source_lines)
    module_header = '"""Pure note-entry helpers extracted from SPINA."""\n\nfrom __future__ import annotations\n\n'
    patched_module = module_header + function_text.lstrip().rstrip() + "\n"

    compile(patched_app, str(APP_PATH), "exec")
    compile(patched_module, str(MODULE_PATH), "exec")
    atomic_write(APP_PATH, patched_app)
    atomic_write(MODULE_PATH, patched_module)

    final_plan = build_plan()
    validate_plan(final_plan)
    if final_plan["state"] != "extracted":
        raise RuntimeError(f"Extraction did not reach expected state: {final_plan}")
    return final_plan


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    plan = apply_extraction() if args.apply else build_plan()
    validate_plan(plan)
    rendered = json.dumps(plan, indent=2, ensure_ascii=False) + "\n"
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
