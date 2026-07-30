#!/usr/bin/env python3
"""Static regression checks for Wave 73 quality and safety fixes."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
LONG_TASK_PATH = ROOT / "spina_app" / "long_task_presentation.py"
WAVE81_INSTALL_MARKER = "# --- BEGIN: Clients feature installer Wave 81 ---"
WAVE82_INSTALL_MARKER = "# --- BEGIN: Data Bank feature installer Wave 82 ---"
LEGACY_CLIENT_REFRESH_BIND = 'setattr(App, "refresh_clients", _spina_perf_refresh_clients)'
LEGACY_DATA_BANK_REFRESH_BIND = 'setattr(App, "refresh_data_grid", _spina_perf_refresh_data_grid)'


def parse(path: Path) -> tuple[str, ast.Module]:
    source = path.read_text(encoding="utf-8")
    return source, ast.parse(source, filename=str(path))


def unique_function(tree: ast.AST, name: str) -> ast.FunctionDef:
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    assert len(matches) == 1, (name, len(matches))
    return matches[0]


def dotted_name(node: ast.AST) -> str:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


app_source, app_tree = parse(APP_PATH)
long_source, long_tree = parse(LONG_TASK_PATH)

call_work = unique_function(long_tree, "_call_work_fn")
work_calls = [
    node
    for node in ast.walk(call_work)
    if isinstance(node, ast.Call) and dotted_name(node.func) == "work_fn"
]
assert work_calls, "long-task helper no longer calls work_fn"
assert not any(
    isinstance(handler, ast.ExceptHandler)
    and any(
        isinstance(child, ast.Call) and dotted_name(child.func) == "work_fn"
        for child in ast.walk(ast.Module(body=handler.body, type_ignores=[]))
    )
    for handler in ast.walk(call_work)
), "work_fn may execute twice after a task failure"

set_password = unique_function(app_tree, "_set_user_password")
assert any(
    isinstance(node, ast.If)
    and any(
        isinstance(child, ast.Call)
        and dotted_name(child.func).endswith("_save_users_db")
        for child in ast.walk(node.test)
    )
    for node in ast.walk(set_password)
), "password save result is not checked"

save_users = unique_function(app_tree, "_save_users_db")
save_segment = ast.get_source_segment(app_source, save_users) or ""
assert "-> bool" in save_segment.splitlines()[0], "account save does not report success"
assert ".bak" in save_segment, "last-known-good account backup is not written"
assert any(
    isinstance(node, ast.Return) and isinstance(node.value, ast.Constant)
    and node.value.value is False
    for node in ast.walk(save_users)
), "account save has no explicit failure result"

load_users = unique_function(app_tree, "_load_users_db")
load_segment = ast.get_source_segment(app_source, load_users) or ""
assert any(
    isinstance(node, ast.ExceptHandler)
    and isinstance(node.type, ast.Name)
    and node.type.id == "FileNotFoundError"
    for node in ast.walk(load_users)
), "missing and corrupt account files are not distinguished"
assert ".bak" in load_segment, "account backup recovery is missing"
assert "_load_error" in load_segment, "unreadable account files do not fail closed"

performance_indexes = unique_function(app_tree, "_spina_perf_ensure_indexes")
perf_segment = ast.get_source_segment(app_source, performance_indexes) or ""
assert "_SPINA_PERF_INDEXES_READY" in perf_segment, "index setup has no one-time guard"
assert "_spina_perf_ensure_indexes(LoanDB(DB_FILE))" not in app_source, (
    "module-scope startup LoanDB connection remains"
)

if WAVE81_INSTALL_MARKER in app_source:
    assert LEGACY_CLIENT_REFRESH_BIND not in app_source, (
        "Wave 73 restored redundant Clients refresh ownership under Wave 81"
    )

if WAVE82_INSTALL_MARKER in app_source:
    assert LEGACY_DATA_BANK_REFRESH_BIND not in app_source, (
        "Wave 73 restored redundant Data Bank refresh ownership under Wave 82"
    )

print("Wave 73 quality safety regression checks passed")
