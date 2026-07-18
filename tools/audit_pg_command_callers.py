#!/usr/bin/env python3
"""Read-only audit for PostgreSQL backup/restore command call flow.

This tool does not edit SPINA. It answers one question before any UI-freeze
cleanup is attempted: which functions call the PostgreSQL command helpers, and
whether those calls appear to be routed through an existing long-task/worker path.
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

APP_FILE = "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
TARGET_NAMES = {
    "_create_postgres_backup_file",
    "_verify_postgres_backup_file",
    "_run_pg_command",
    "_find_postgres_exe",
    "_pg_env",
}
LONG_TASK_NAMES = {"_run_long_task", "run_long_task", "threading.Thread", "Thread"}
PROTECTED_TERMS = {
    "backup",
    "restore",
    "postgres",
    "pg_dump",
    "pg_restore",
    "database",
    "payment",
    "balance",
    "7x7",
    "collector",
    "report",
    "pdf",
    "renew",
    "cash",
}


def _call_name(func: ast.AST) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        base = _call_name(func.value)
        return f"{base}.{func.attr}" if base else func.attr
    if isinstance(func, ast.Call):
        return _call_name(func.func)
    if isinstance(func, ast.Subscript):
        return _call_name(func.value)
    return ""


def _short_call_name(name: str) -> str:
    return name.rsplit(".", 1)[-1] if name else ""


def _contains_name(node: ast.AST, names: set[str]) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            call_name = _call_name(child.func)
            short = _short_call_name(call_name)
            if call_name in names or short in names:
                return True
    return False


def _context(lines: list[str], line: int, radius: int) -> list[dict[str, Any]]:
    start = max(1, line - radius)
    end = min(len(lines), line + radius)
    return [
        {"line": i, "text": lines[i - 1].rstrip("\n")}
        for i in range(start, end + 1)
    ]


def _protected_context(lines: list[str], line: int, radius: int) -> bool:
    text = "\n".join(x["text"].lower() for x in _context(lines, line, radius))
    return any(term in text for term in PROTECTED_TERMS)


def _function_record(node: ast.AST, class_name: str | None = None) -> dict[str, Any]:
    name = getattr(node, "name", "<unknown>")
    qualname = f"{class_name}.{name}" if class_name else name
    return {
        "name": name,
        "qualname": qualname,
        "line": getattr(node, "lineno", None),
        "end_line": getattr(node, "end_lineno", getattr(node, "lineno", None)),
        "contains_long_task_call": _contains_name(node, LONG_TASK_NAMES),
        "worker_like_name": any(tok in qualname.lower() for tok in ("worker", "thread", "long_task", "background")),
    }


def audit(path: Path, radius: int = 10) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8", errors="replace")
    lines = source.splitlines()
    tree = ast.parse(source, filename=str(path))

    definitions: dict[str, list[dict[str, Any]]] = {name: [] for name in TARGET_NAMES}
    call_sites: list[dict[str, Any]] = []

    stack: list[dict[str, Any]] = []

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.class_stack: list[str] = []

        def visit_ClassDef(self, node: ast.ClassDef) -> Any:  # noqa: N802
            self.class_stack.append(node.name)
            self.generic_visit(node)
            self.class_stack.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:  # noqa: N802
            class_name = self.class_stack[-1] if self.class_stack else None
            rec = _function_record(node, class_name)
            if node.name in definitions:
                definitions[node.name].append(rec)
            stack.append(rec)
            self.generic_visit(node)
            stack.pop()

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:  # noqa: N802
            self.visit_FunctionDef(node)  # type: ignore[arg-type]

        def visit_Call(self, node: ast.Call) -> Any:  # noqa: N802
            full = _call_name(node.func)
            short = _short_call_name(full)
            if short in TARGET_NAMES:
                caller = stack[-1] if stack else {
                    "name": "<module>",
                    "qualname": "<module>",
                    "line": 1,
                    "end_line": len(lines),
                    "contains_long_task_call": False,
                    "worker_like_name": False,
                }
                call_sites.append({
                    "line": getattr(node, "lineno", None),
                    "end_line": getattr(node, "end_lineno", getattr(node, "lineno", None)),
                    "target": short,
                    "call_text": full,
                    "caller": caller,
                    "caller_uses_long_task": bool(caller.get("contains_long_task_call")),
                    "caller_worker_like": bool(caller.get("worker_like_name")),
                    "protected_context": _protected_context(lines, getattr(node, "lineno", 1), radius),
                    "context": _context(lines, getattr(node, "lineno", 1), radius),
                })
            self.generic_visit(node)

    Visitor().visit(tree)

    high_review = [
        c for c in call_sites
        if c["target"] in {"_create_postgres_backup_file", "_verify_postgres_backup_file", "_run_pg_command"}
        and not c["caller_uses_long_task"]
        and not c["caller_worker_like"]
    ]

    return {
        "file": str(path),
        "line_count": len(lines),
        "target_names": sorted(TARGET_NAMES),
        "definition_count": sum(len(v) for v in definitions.values()),
        "definitions": definitions,
        "call_site_count": len(call_sites),
        "high_review_call_site_count": len(high_review),
        "call_sites": call_sites,
        "recommendations": [
            "Read-only call-flow audit only; no app source changes are made.",
            "Treat protected PostgreSQL backup/restore command paths as review-only until manually confirmed.",
            "Prefer routing confirmed long-running backup/restore work through an existing long-task/worker path instead of changing command arguments first.",
            "Do not touch reports, PDFs, payments, balances, 7x7, renewals, collectors, database migrations, cash-control, or report math from this audit alone.",
            "If a UI-freeze fix is approved, change one backup/restore command family at a time and smoke-test backup, verify backup, and restore-test flows.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit PostgreSQL command helper call flow.")
    parser.add_argument("path", nargs="?", default=APP_FILE)
    parser.add_argument("--json", dest="json_path", default=None)
    parser.add_argument("--context-radius", type=int, default=10)
    args = parser.parse_args()

    report = audit(Path(args.path), radius=max(0, args.context_radius))
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.json_path:
        Path(args.json_path).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
