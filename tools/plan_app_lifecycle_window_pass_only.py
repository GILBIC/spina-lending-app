#!/usr/bin/env python3
"""Read-only planner for App lifecycle/window pass-only exception handlers.

This tool narrows review to small startup/window/root-closing fallback handlers.
It never edits the SPINA app and never approves cleanup.
"""

from __future__ import annotations

import argparse
import ast
import json
from collections import Counter
from pathlib import Path
from typing import Any

APP_FILE = "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"

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


def _name(node: ast.AST | None) -> str:
    if node is None:
        return "bare"
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    try:
        return ast.unparse(node)
    except Exception:
        return type(node).__name__


def _is_pass_only(handler: ast.ExceptHandler) -> bool:
    return len(handler.body) == 1 and isinstance(handler.body[0], ast.Pass)


def _context(lines: list[str], lineno: int, end_lineno: int, radius: int) -> list[dict[str, Any]]:
    start = max(1, lineno - radius)
    end = min(len(lines), end_lineno + radius)
    return [{"line": i, "text": lines[i - 1]} for i in range(start, end + 1)]


def _context_text(ctx: list[dict[str, Any]]) -> str:
    return "\n".join(str(item["text"]) for item in ctx).lower()


def _protected(ctx_text: str) -> bool:
    return any(word.lower() in ctx_text for word in PROTECTED_WORDS)


def _classify(scope: str, handler: str, ctx_text: str) -> str:
    if handler != "Exception":
        return "non_app_lifecycle_reference"

    if scope == "App.__init__" and (
        "center on screen" in ctx_text
        or "root.geometry" in ctx_text
        or "root.minsize" in ctx_text
        or "winfo_screenwidth" in ctx_text
        or "winfo_screenheight" in ctx_text
    ):
        return "startup_window_geometry_review"

    if scope == "App._run_long_task._watchdog" and (
        "root is likely closing" in ctx_text
        or "self.root.after" in ctx_text
        or "_watchdog" in ctx_text
    ):
        return "root_closing_watchdog_review"

    if "winfo_exists" in ctx_text and "root" in ctx_text and "after(" in ctx_text:
        return "root_lifecycle_reference_review"

    return "non_app_lifecycle_reference"


class PassOnlyVisitor(ast.NodeVisitor):
    def __init__(self, lines: list[str], radius: int) -> None:
        self.lines = lines
        self.radius = radius
        self.stack: list[str] = []
        self.sites: list[dict[str, Any]] = []

    def _scope(self) -> str:
        return ".".join(self.stack) if self.stack else "<module>"

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_Try(self, node: ast.Try) -> Any:
        scope = self._scope()
        for handler in node.handlers:
            if not _is_pass_only(handler):
                continue
            lineno = getattr(handler, "lineno", 0) or 0
            end_lineno = getattr(handler, "end_lineno", lineno) or lineno
            ctx = _context(self.lines, lineno, end_lineno, self.radius)
            ctx_text = _context_text(ctx)
            handler_name = _name(handler.type)
            group = _classify(scope, handler_name, ctx_text)

            self.sites.append(
                {
                    "line": lineno,
                    "end_line": end_lineno,
                    "scope": scope,
                    "handler": handler_name,
                    "app_lifecycle_window": group != "non_app_lifecycle_reference",
                    "protected_context": _protected(ctx_text),
                    "group": group,
                    "selected_for_cleanup_plan": False,
                    "recommended_action": "Review only. This planner does not approve cleanup.",
                    "context": ctx,
                }
            )
        self.generic_visit(node)


def build_report(path: Path, radius: int) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    tree = ast.parse(text)

    visitor = PassOnlyVisitor(lines, radius)
    visitor.visit(tree)

    sites = visitor.sites
    app_sites = [s for s in sites if s["app_lifecycle_window"]]

    return {
        "file": str(path),
        "line_count": len(lines),
        "context_radius": radius,
        "pass_only_exception_count": len(sites),
        "app_lifecycle_window_pass_only_count": len(app_sites),
        "non_app_lifecycle_window_pass_only_count": len(sites) - len(app_sites),
        "selected_cleanup_candidate_count": 0,
        "group_counts": dict(Counter(s["group"] for s in sites)),
        "app_lifecycle_scope_counts": dict(Counter(s["scope"] for s in app_sites)),
        "safety": {
            "read_only": True,
            "app_source_modified": False,
            "cleanup_approved": False,
            "protected_words_used": PROTECTED_WORDS,
            "note": (
                "This report narrows to App lifecycle/window fallback pass-only "
                "handlers only. It does not approve cleanup."
            ),
        },
        "app_lifecycle_window_sites": app_sites,
        "recommendations": [
            "Do not apply cleanup from this report alone.",
            "Treat startup geometry and root-closing watchdog fallbacks as review-only unless a future exact cleanup tool proves otherwise.",
            "Only consider a future cleanup tool for exact reviewed App lifecycle/window handlers.",
            "Do not touch business logic, reports, payments, balances, database, backups, role/access, login/auth, or report math.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", default=APP_FILE, help="SPINA app source file")
    parser.add_argument("--json", dest="json_path", help="Write report JSON to this path")
    parser.add_argument("--context-radius", type=int, default=8)
    args = parser.parse_args()

    report = build_report(Path(args.file), args.context_radius)
    payload = json.dumps(report, indent=2, ensure_ascii=False)

    if args.json_path:
        Path(args.json_path).write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
