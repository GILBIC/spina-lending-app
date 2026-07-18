#!/usr/bin/env python3
"""Show source context around potentially blocking UI calls.

Read-only helper for SPINA cleanup work. It does not modify the app source.
It complements tools/audit_blocking_ui_calls.py by including surrounding source
lines so a human can decide whether a candidate is actually safe to change.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

DEFAULT_SOURCE = "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"

PROTECTED_TERMS = {
    "payment", "payments", "balance", "balances", "7x7", "x7", "interest",
    "principal", "renew", "renewal", "collector", "collectors", "route",
    "ledger", "statement", "report", "reports", "pdf", "cash", "cash-control",
    "cash_control", "databank", "data bank", "notes", "note", "transaction",
    "transactions", "loan", "loandb", "database", "postgres", "backup", "restore",
    "gcash", "receipt", "client", "clients",
}

UI_SCOPE_HINTS = (
    "app.", "dialog", "window", "button", "tab", "ui", "menu", "tree",
    "frame", "refresh", "open_", "show_", "build_", "create_",
)

WORKER_SCOPE_HINTS = (
    "worker", "thread", "background", "long_task", "run_long_task", "after_idle",
    "async", "executor", "queue",
)


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


def _is_blocking_call(node: ast.Call) -> str | None:
    name = _call_name(node.func)
    if name in {"time.sleep", "subprocess.run"}:
        return name
    return None


def _span_for_node(node: ast.AST) -> tuple[int, int]:
    start = int(getattr(node, "lineno", 0) or 0)
    end = int(getattr(node, "end_lineno", start) or start)
    return start, end


def _context(lines: list[str], line_no: int, radius: int) -> list[dict[str, Any]]:
    start = max(1, line_no - radius)
    end = min(len(lines), line_no + radius)
    return [
        {"line": idx, "text": lines[idx - 1].rstrip("\n")}
        for idx in range(start, end + 1)
    ]


def _contains_protected_text(context_lines: list[dict[str, Any]]) -> bool:
    text = "\n".join(str(item.get("text", "")) for item in context_lines).lower()
    return any(term in text for term in PROTECTED_TERMS)


def _severity(call: str, scope: str, worker_like: bool, ui_like: bool) -> str:
    if worker_like:
        return "likely_background_or_worker"
    if call == "subprocess.run" and ui_like:
        return "likely_ui_blocker"
    if call == "subprocess.run":
        return "possible_ui_blocker"
    if call == "time.sleep" and ui_like:
        return "possible_ui_blocker"
    return "review"


class BlockingContextVisitor(ast.NodeVisitor):
    def __init__(self, lines: list[str], radius: int) -> None:
        self.lines = lines
        self.radius = radius
        self.scope_stack: list[str] = []
        self.calls: list[dict[str, Any]] = []

    def _scope_name(self) -> str:
        return ".".join(self.scope_stack) if self.scope_stack else "<module>"

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self.visit_FunctionDef(node)  # same stack handling

    def visit_Call(self, node: ast.Call) -> Any:
        call = _is_blocking_call(node)
        if call:
            start, end = _span_for_node(node)
            scope = self._scope_name()
            scope_lower = scope.lower()
            worker_like = any(hint in scope_lower for hint in WORKER_SCOPE_HINTS)
            ui_like = scope.startswith("App.") or any(hint in scope_lower for hint in UI_SCOPE_HINTS)
            ctx = _context(self.lines, start, self.radius)
            protected_context = _contains_protected_text(ctx)
            self.calls.append({
                "line": start,
                "end_line": end,
                "call": call,
                "scope": scope,
                "worker_like_scope": worker_like,
                "ui_like_scope": ui_like,
                "protected_context": protected_context,
                "severity": _severity(call, scope, worker_like, ui_like),
                "context": ctx,
            })
        self.generic_visit(node)


def inspect_source(path: Path, radius: int) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source, filename=str(path))
    visitor = BlockingContextVisitor(lines, radius)
    visitor.visit(tree)

    calls = visitor.calls
    return {
        "file": str(path),
        "line_count": len(lines),
        "context_radius": radius,
        "blocking_call_count": len(calls),
        "ui_blocking_candidate_count": sum(1 for c in calls if c.get("severity") in {"likely_ui_blocker", "possible_ui_blocker"}),
        "protected_context_count": sum(1 for c in calls if c.get("protected_context")),
        "calls": calls,
        "recommendations": [
            "Read-only context inspection only; no app source changes are made.",
            "Review the surrounding lines before changing any blocking call.",
            "Prefer moving long subprocess work to an existing worker/long-task path instead of editing UI code directly.",
            "Do not touch reports, PDFs, payments, balances, 7x7, renewals, collectors, database migrations, cash-control, or report math from this context report alone.",
            "If a candidate is confirmed safe, change one call family at a time and smoke-test SPINA after each change.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect source context around blocking UI call candidates.")
    parser.add_argument("source", nargs="?", default=DEFAULT_SOURCE)
    parser.add_argument("--context", type=int, default=12, help="number of surrounding lines to include before and after each call")
    parser.add_argument("--json", dest="json_path", default=None, help="write report JSON to this path")
    args = parser.parse_args()

    report = inspect_source(Path(args.source), max(1, int(args.context)))
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.json_path:
        Path(args.json_path).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
