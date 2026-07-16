#!/usr/bin/env python3
"""Static regression checks for the bug/efficiency review fixes."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

SOURCE = Path(sys.argv[1])
source = SOURCE.read_text(encoding="utf-8")
tree = ast.parse(source, filename=str(SOURCE))


def definitions(name: str):
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    ]


def dotted_name(node: ast.AST) -> str:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def module_calls(node: ast.AST):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
        return
    if isinstance(node, ast.Call):
        yield node
    for child in ast.iter_child_nodes(node):
        yield from module_calls(child)


call_work = definitions("_call_work_fn")[0]
assert not any(
    isinstance(handler, ast.ExceptHandler)
    and any(
        isinstance(child, ast.Call) and dotted_name(child.func) == "work_fn"
        for child in ast.walk(ast.Module(body=handler.body, type_ignores=[]))
    )
    for handler in ast.walk(call_work)
), "work_fn may execute twice after a task failure"

set_password = definitions("_set_user_password")[0]
assert any(
    isinstance(node, ast.If)
    and any(
        isinstance(child, ast.Call)
        and dotted_name(child.func).endswith("_save_users_db")
        for child in ast.walk(node.test)
    )
    for node in ast.walk(set_password)
), "password save result is not checked"

load_users = definitions("_load_users_db")[0]
assert any(
    isinstance(node, ast.ExceptHandler)
    and isinstance(node.type, ast.Name)
    and node.type.id == "FileNotFoundError"
    for node in ast.walk(load_users)
), "missing and corrupt users files are not distinguished"
assert ".bak" in ast.get_source_segment(source, load_users), "users backup recovery missing"

performance_indexes = definitions("_spina_perf_ensure_indexes")[0]
assert "_SPINA_PERF_INDEXES_READY" in ast.get_source_segment(
    source, performance_indexes
), "index setup has no one-time guard"

for statement in tree.body:
    assert not any(
        dotted_name(call.func) == "LoanDB" for call in module_calls(statement)
    ), "module-scope LoanDB startup connection remains"

print("quality fix regression checks passed")
