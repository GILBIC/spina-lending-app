#!/usr/bin/env python3
"""Read-only planner for queue.Empty pass-only exception handlers in SPINA.

This tool intentionally does not modify the SPINA app. It narrows review to
pass-only handlers for queue.Empty, especially the UI queue pump "nothing
pending" control-flow handler. It does not approve cleanup.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

DEFAULT_APP = "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
CONTEXT_RADIUS = 8

PROTECTED_WORDS = [
    "7x7",
    "7×7",
    "apply_role_access",
    "backup",
    "balance",
    "cash control",
    "collector",
    "database",
    "interest",
    "ledger",
    "migration",
    "payment",
    "payroll",
    "pdf",
    "pg_",
    "postgres",
    "principal",
    "receipt",
    "renew",
    "report",
    "restore",
    "role_access",
    "route",
    "statement",
    "transaction",
]


def _handler_name(node: ast.AST | None) -> str:
    if node is None:
        return "bare"
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = _handler_name(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    if isinstance(node, ast.Tuple):
        return ",".join(_handler_name(elt) for elt in node.elts)
    return node.__class__.__name__


def _is_pass_only(handler: ast.ExceptHandler) -> bool:
    return len(handler.body) == 1 and isinstance(handler.body[0], ast.Pass)


def _context(lines: list[str], line_no: int, radius: int) -> list[dict[str, Any]]:
    start = max(1, line_no - radius)
    end = min(len(lines), line_no + radius)
    return [
        {"line": i, "text": lines[i - 1].rstrip("\n")}
        for i in range(start, end + 1)
    ]


def _contains_protected_word(text: str) -> bool:
    low = text.lower()
    return any(word.lower() in low for word in PROTECTED_WORDS)


class PassOnlyVisitor(ast.NodeVisitor):
    def __init__(self, lines: list[str], radius: int) -> None:
        self.lines = lines
        self.radius = radius
        self.scope: list[str] = []
        self.pass_only_sites: list[dict[str, Any]] = []

    def _scope_name(self) -> str:
        return ".".join(self.scope) if self.scope else "<module>"

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> Any:
        if _is_pass_only(node):
            handler = _handler_name(node.type)
            line_no = int(getattr(node, "lineno", 0) or 0)
            end_line = int(getattr(node, "end_lineno", line_no) or line_no)
            ctx = _context(self.lines, line_no, self.radius)
            context_text = "\n".join(item["text"] for item in ctx)
            scope = self._scope_name()
            is_queue_empty = handler == "queue.Empty" or handler.endswith(".Empty")
            ui_queue_pump = (
                is_queue_empty
                and "_start_ui_queue_pump" in scope
                and ("nothing pending" in context_text.lower() or "ui_queue" in context_text.lower())
            )
            group = "non_queue_reference"
            if is_queue_empty:
                group = "queue_empty_ui_pump_review" if ui_queue_pump else "queue_empty_other_review"
            self.pass_only_sites.append(
                {
                    "line": line_no,
                    "end_line": end_line,
                    "scope": scope,
                    "handler": handler,
                    "queue_empty": is_queue_empty,
                    "ui_queue_pump_control_flow": ui_queue_pump,
                    "protected_context": _contains_protected_word(context_text),
                    "group": group,
                    "selected_for_cleanup_plan": False,
                    "recommended_action": "Review only. This planner does not approve cleanup.",
                    "context": ctx,
                }
            )
        self.generic_visit(node)


def build_report(app_path: Path, radius: int) -> dict[str, Any]:
    source = app_path.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source)
    visitor = PassOnlyVisitor(lines, radius)
    visitor.visit(tree)

    pass_only_sites = visitor.pass_only_sites
    queue_sites = [site for site in pass_only_sites if site["queue_empty"]]
    group_counts: dict[str, int] = {}
    queue_scope_counts: dict[str, int] = {}
    for site in pass_only_sites:
        group_counts[site["group"]] = group_counts.get(site["group"], 0) + 1
    for site in queue_sites:
        scope = str(site["scope"])
        queue_scope_counts[scope] = queue_scope_counts.get(scope, 0) + 1

    return {
        "file": str(app_path),
        "line_count": len(lines),
        "context_radius": radius,
        "pass_only_exception_count": len(pass_only_sites),
        "queue_empty_pass_only_count": len(queue_sites),
        "non_queue_empty_pass_only_count": len(pass_only_sites) - len(queue_sites),
        "selected_cleanup_candidate_count": 0,
        "group_counts": group_counts,
        "queue_scope_counts": queue_scope_counts,
        "safety": {
            "read_only": True,
            "app_source_modified": False,
            "cleanup_approved": False,
            "protected_words_used": PROTECTED_WORDS,
            "note": "This report narrows to queue.Empty pass-only handlers only. It does not approve cleanup.",
        },
        "queue_empty_sites": queue_sites,
        "recommendations": [
            "Do not apply cleanup from this report alone.",
            "Treat queue.Empty as normal empty-queue control flow unless a future exact cleanup tool proves otherwise.",
            "Only consider a future cleanup tool for exact reviewed queue.Empty handlers.",
            "Do not touch business logic, reports, payments, balances, database, backups, role/access, login/auth, or report math.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan queue.Empty pass-only review targets without editing SPINA.")
    parser.add_argument("app", nargs="?", default=DEFAULT_APP)
    parser.add_argument("--json", dest="json_path", default=None)
    parser.add_argument("--context", type=int, default=CONTEXT_RADIUS)
    args = parser.parse_args()

    app_path = Path(args.app)
    report = build_report(app_path, args.context)
    payload = json.dumps(report, indent=2, ensure_ascii=False)
    if args.json_path:
        Path(args.json_path).write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
