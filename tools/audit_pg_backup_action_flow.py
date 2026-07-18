#!/usr/bin/env python3
"""Read-only audit for PostgreSQL backup/verify/restore UI action flow.

This tool inspects the SPINA app source to answer one narrow question:
Are PostgreSQL backup/verify/restore command helpers reached from UI actions through
an existing long-task/worker path?

It does not modify source files.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

APP_FILE = "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"

TARGETS = {
    "_create_postgres_backup_file",
    "_verify_postgres_backup_file",
    "_restore_backup_to_test_database",
    "_run_pg_command",
    "_run_long_task",
}

PROTECTED_TERMS = {
    "postgres", "pg_", "backup", "restore", "database", "db", "password",
    "pg_dump", "pg_restore", "dropdb", "createdb", "spina_restore_test",
}


def read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def qualname(stack: list[ast.AST], node: ast.AST) -> str:
    parts: list[str] = []
    for item in stack:
        if isinstance(item, ast.ClassDef):
            parts.append(item.name)
        elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            parts.append(item.name)
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        parts.append(node.name)
    return ".".join(parts) if parts else "<module>"


def func_name_from_call(node: ast.Call) -> str | None:
    fn = node.func
    if isinstance(fn, ast.Attribute):
        return fn.attr
    if isinstance(fn, ast.Name):
        return fn.id
    return None


def call_text(lines: list[str], node: ast.AST) -> str:
    try:
        line = lines[getattr(node, "lineno", 1) - 1]
        return line.strip()
    except Exception:
        return ""


def text_range(lines: list[str], start: int, end: int) -> str:
    lo = max(1, start)
    hi = min(len(lines), end)
    return "\n".join(lines[lo - 1:hi])


def has_call(node: ast.AST, names: set[str]) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            name = func_name_from_call(child)
            if name in names:
                return True
    return False


def context(lines: list[str], line: int, radius: int = 12) -> list[dict[str, Any]]:
    lo = max(1, line - radius)
    hi = min(len(lines), line + radius)
    return [{"line": n, "text": lines[n - 1]} for n in range(lo, hi + 1)]


def protected_context(lines: list[str], start: int, end: int, radius: int = 8) -> bool:
    txt = text_range(lines, start - radius, end + radius).lower()
    return any(term in txt for term in PROTECTED_TERMS)


class Visitor(ast.NodeVisitor):
    def __init__(self, lines: list[str]) -> None:
        self.lines = lines
        self.stack: list[ast.AST] = []
        self.definitions: dict[str, list[dict[str, Any]]] = {}
        self.call_sites: list[dict[str, Any]] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        self.stack.append(node)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self._visit_function(node)

    def _visit_function(self, node: ast.AST) -> None:
        name = getattr(node, "name", "")
        qn = qualname(self.stack, node)
        if name in TARGETS or name in {"backup_now", "verify", "restore_test", "open_backup_history_window"}:
            start = int(getattr(node, "lineno", 0) or 0)
            end = int(getattr(node, "end_lineno", start) or start)
            self.definitions.setdefault(name, []).append({
                "name": name,
                "qualname": qn,
                "line": start,
                "end_line": end,
                "contains_run_long_task": has_call(node, {"_run_long_task"}),
                "contains_target_helper_call": has_call(node, TARGETS - {"_run_long_task"}),
                "worker_like_name": any(tok in name.lower() for tok in ("worker", "thread", "task", "background")),
                "protected_context": protected_context(self.lines, start, end),
            })
        self.stack.append(node)
        self.generic_visit(node)
        self.stack.pop()

    def visit_Call(self, node: ast.Call) -> Any:
        name = func_name_from_call(node)
        if name in TARGETS:
            caller_node = next((s for s in reversed(self.stack) if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef))), None)
            caller_name = getattr(caller_node, "name", "<module>") if caller_node is not None else "<module>"
            caller_qn = qualname([s for s in self.stack if s is not caller_node], caller_node) if caller_node is not None else "<module>"
            caller_line = int(getattr(caller_node, "lineno", 0) or 0) if caller_node is not None else None
            caller_end = int(getattr(caller_node, "end_lineno", caller_line or 0) or 0) if caller_node is not None else None
            caller_uses_long_task = has_call(caller_node, {"_run_long_task"}) if caller_node is not None else False
            target_inside_long_task_call = self._is_inside_run_long_task_argument(node)
            line = int(getattr(node, "lineno", 0) or 0)
            end = int(getattr(node, "end_lineno", line) or line)
            self.call_sites.append({
                "line": line,
                "end_line": end,
                "target": name,
                "call_text": call_text(self.lines, node),
                "caller": {
                    "name": caller_name,
                    "qualname": caller_qn,
                    "line": caller_line,
                    "end_line": caller_end,
                    "contains_run_long_task": caller_uses_long_task,
                    "worker_like_name": any(tok in str(caller_name).lower() for tok in ("worker", "thread", "task", "background")),
                },
                "caller_uses_long_task": caller_uses_long_task,
                "target_inside_run_long_task_call": target_inside_long_task_call,
                "protected_context": protected_context(self.lines, line, end),
                "context": context(self.lines, line),
            })
        self.generic_visit(node)

    def _is_inside_run_long_task_argument(self, node: ast.AST) -> bool:
        # Best-effort lexical check: if a target call appears inside the same caller
        # that invokes _run_long_task, the caller-level flag is usually enough. This
        # marker is conservative and only true for direct nested Call ancestors, which
        # Python AST does not expose parent links for here. Keep false rather than
        # overclaiming.
        return False


def build_report(app_path: Path) -> dict[str, Any]:
    lines = read_lines(app_path)
    tree = ast.parse("\n".join(lines), filename=str(app_path))
    visitor = Visitor(lines)
    visitor.visit(tree)

    helper_calls = [c for c in visitor.call_sites if c["target"] != "_run_long_task"]
    outer_worker_calls = [
        c for c in helper_calls
        if c["caller_uses_long_task"] or c["caller"]["worker_like_name"]
    ]
    direct_helper_calls = [
        c for c in helper_calls
        if not c["caller_uses_long_task"] and not c["caller"]["worker_like_name"]
    ]

    return {
        "file": str(app_path),
        "line_count": len(lines),
        "target_names": sorted(TARGETS),
        "definition_count": sum(len(v) for v in visitor.definitions.values()),
        "definitions": visitor.definitions,
        "call_site_count": len(visitor.call_sites),
        "helper_call_site_count": len(helper_calls),
        "worker_routed_helper_call_count": len(outer_worker_calls),
        "direct_helper_call_count": len(direct_helper_calls),
        "direct_helper_calls": direct_helper_calls,
        "call_sites": visitor.call_sites,
        "recommendations": [
            "Read-only action-flow audit only; no app source changes are made.",
            "Backup/verify/restore helpers are protected; do not edit them from this audit alone.",
            "If backup or restore-test is not worker-routed, prefer routing the outer UI action through the existing _run_long_task path.",
            "Do not touch reports, PDFs, payments, balances, 7x7, renewals, collectors, database migrations, cash-control, or report math from this audit alone.",
            "If a UI-freeze fix is approved, change one outer action flow at a time and smoke-test Backup, Verify Backup, and Restore Test Database.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app", nargs="?", default=APP_FILE)
    parser.add_argument("--json", dest="json_path")
    args = parser.parse_args()

    report = build_report(Path(args.app))
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.json_path:
        Path(args.json_path).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
