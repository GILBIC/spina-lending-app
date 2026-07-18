#!/usr/bin/env python3
"""Read-only audit for potentially blocking calls in the SPINA UI app.

This tool does not edit the app. It scans for calls such as time.sleep and
subprocess.run, records their scope, and marks the ones that appear to be in
normal UI paths rather than obvious worker/thread helper code.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

DEFAULT_APP_FILE = "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"

BLOCKING_CALLS = {
    "time.sleep",
    "subprocess.run",
    "subprocess.call",
    "subprocess.check_call",
    "subprocess.check_output",
    "subprocess.Popen",
}

WORKER_HINTS = (
    "worker",
    "thread",
    "background",
    "async",
    "queue",
    "executor",
    "long_task",
    "after_idle",
)

UI_HINTS = (
    "dialog",
    "tab",
    "window",
    "button",
    "click",
    "refresh",
    "open_",
    "show_",
    "build_",
    "import",
    "export",
    "backup",
    "restore",
)


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Attribute):
        owner = _call_name(node.value)
        if owner:
            return f"{owner}.{node.attr}"
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


def _nearest_scope(scope_stack: list[dict[str, Any]], kind: str) -> dict[str, Any] | None:
    for item in reversed(scope_stack):
        if item.get("kind") == kind:
            return item
    return None


def _scope_name(scope_stack: list[dict[str, Any]]) -> str:
    class_scope = _nearest_scope(scope_stack, "class")
    function_scope = _nearest_scope(scope_stack, "function")
    if class_scope and function_scope:
        return f"{class_scope['name']}.{function_scope['name']}"
    if function_scope:
        return str(function_scope["name"])
    return "<module>"


def _has_hint(text: str, hints: tuple[str, ...]) -> bool:
    low = text.lower()
    return any(hint in low for hint in hints)


class BlockingCallVisitor(ast.NodeVisitor):
    def __init__(self, lines: list[str]) -> None:
        self.lines = lines
        self.scope_stack: list[dict[str, Any]] = []
        self.calls: list[dict[str, Any]] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        self.scope_stack.append({"kind": "class", "name": node.name, "line": node.lineno})
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self.scope_stack.append({"kind": "function", "name": node.name, "line": node.lineno})
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self.scope_stack.append({"kind": "function", "name": node.name, "line": node.lineno})
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_Call(self, node: ast.Call) -> Any:
        name = _call_name(node.func)
        if name in BLOCKING_CALLS:
            scope = _scope_name(self.scope_stack)
            code_line = self.lines[node.lineno - 1].strip() if 0 < node.lineno <= len(self.lines) else ""
            scope_text = " ".join(str(item.get("name", "")) for item in self.scope_stack)
            worker_like = _has_hint(scope_text, WORKER_HINTS)
            ui_like = _has_hint(scope, UI_HINTS)
            candidate = not worker_like
            severity = "review"
            if candidate and ui_like:
                severity = "likely_ui_blocker"
            elif candidate:
                severity = "possible_ui_blocker"
            self.calls.append(
                {
                    "line": node.lineno,
                    "call": name,
                    "scope": scope,
                    "worker_like_scope": worker_like,
                    "ui_like_scope": ui_like,
                    "ui_blocking_candidate": candidate,
                    "severity": severity,
                    "text": code_line,
                }
            )
        self.generic_visit(node)


def build_report(app_file: Path) -> dict[str, Any]:
    text = app_file.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    tree = ast.parse(text, filename=str(app_file))
    visitor = BlockingCallVisitor(lines)
    visitor.visit(tree)
    calls = sorted(visitor.calls, key=lambda item: (item["line"], item["call"]))
    candidates = [item for item in calls if item["ui_blocking_candidate"]]
    return {
        "file": str(app_file),
        "line_count": len(lines),
        "blocking_call_count": len(calls),
        "ui_blocking_candidate_count": len(candidates),
        "calls": calls,
        "recommendations": [
            "Read-only audit only; no app source changes are made.",
            "Review each blocking call in context before changing behavior.",
            "Prefer moving long subprocess work to an existing worker/long-task path instead of editing UI code directly.",
            "Do not touch reports, PDFs, payments, balances, 7x7, renewals, collectors, database migrations, or cash-control logic from this report alone.",
            "If a candidate is confirmed safe, change one call family at a time and smoke-test SPINA after each change.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit potential blocking UI calls in the SPINA app.")
    parser.add_argument("app_file", nargs="?", default=DEFAULT_APP_FILE)
    parser.add_argument("--json", dest="json_path", help="Write the report to this JSON file.")
    args = parser.parse_args()

    app_file = Path(args.app_file)
    report = build_report(app_file)
    payload = json.dumps(report, indent=2, ensure_ascii=False)
    if args.json_path:
        Path(args.json_path).write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
