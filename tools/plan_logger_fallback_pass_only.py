#!/usr/bin/env python3
"""Read-only planner for logger fallback pass-only exception handlers.

This tool is intentionally conservative. It scans the SPINA app for pass-only
exception handlers and reports only handlers inside the tiny logger fallback
helpers. It does not edit the app and it never approves cleanup.
"""

from __future__ import annotations

import argparse
import ast
import json
from collections import Counter
from pathlib import Path
from typing import Any

APP_FILE = "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"

LOGGER_FALLBACK_SCOPES = {
    "_log_exc",
    "_log_suppressed_once",
}

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


def _handler_name(node: ast.ExceptHandler) -> str:
    if node.type is None:
        return "bare"
    if isinstance(node.type, ast.Name):
        return node.type.id
    if isinstance(node.type, ast.Attribute):
        return node.type.attr
    try:
        return ast.unparse(node.type)
    except Exception:
        return type(node.type).__name__


def _is_pass_only(node: ast.ExceptHandler) -> bool:
    return len(node.body) == 1 and isinstance(node.body[0], ast.Pass)


def _context(lines: list[str], lineno: int, end_lineno: int, radius: int) -> list[dict[str, Any]]:
    start = max(1, lineno - radius)
    end = min(len(lines), end_lineno + radius)
    out: list[dict[str, Any]] = []
    for line_no in range(start, end + 1):
        out.append({"line": line_no, "text": lines[line_no - 1].rstrip("\n")})
    return out


def _scope_name(scope: list[str]) -> str:
    return ".".join(scope) if scope else "<module>"


class PassOnlyVisitor(ast.NodeVisitor):
    def __init__(self, lines: list[str], radius: int) -> None:
        self.lines = lines
        self.radius = radius
        self.scope: list[str] = []
        self.sites: list[dict[str, Any]] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:  # noqa: ANN401
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:  # noqa: ANN401
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:  # noqa: ANN401
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_Try(self, node: ast.Try) -> Any:  # noqa: ANN401
        current_scope = _scope_name(self.scope)
        for handler in node.handlers:
            if not _is_pass_only(handler):
                continue
            lineno = int(getattr(handler, "lineno", 0) or 0)
            end_lineno = int(getattr(handler, "end_lineno", lineno) or lineno)
            handler_text = _handler_name(handler)
            context = _context(self.lines, lineno, end_lineno, self.radius)
            context_blob = "\n".join(item["text"] for item in context).lower()
            protected_context = any(word.lower() in context_blob for word in PROTECTED_WORDS)
            logger_fallback = current_scope in LOGGER_FALLBACK_SCOPES
            group = "logger_fallback_review" if logger_fallback else "non_logger_reference"
            self.sites.append(
                {
                    "line": lineno,
                    "end_line": end_lineno,
                    "scope": current_scope,
                    "handler": handler_text,
                    "logger_fallback": logger_fallback,
                    "protected_context": protected_context,
                    "group": group,
                    "selected_for_cleanup_plan": False,
                    "recommended_action": "Review only. This planner does not approve cleanup.",
                    "context": context,
                }
            )
        self.generic_visit(node)


def build_report(app_path: Path, radius: int) -> dict[str, Any]:
    source = app_path.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source, filename=str(app_path))
    visitor = PassOnlyVisitor(lines, radius)
    visitor.visit(tree)

    pass_sites = visitor.sites
    logger_sites = [site for site in pass_sites if site["logger_fallback"]]
    group_counts = Counter(site["group"] for site in pass_sites)
    logger_scope_counts = Counter(site["scope"] for site in logger_sites)

    return {
        "file": str(app_path),
        "line_count": len(lines),
        "context_radius": radius,
        "pass_only_exception_count": len(pass_sites),
        "logger_fallback_pass_only_count": len(logger_sites),
        "non_logger_pass_only_count": len(pass_sites) - len(logger_sites),
        "selected_cleanup_candidate_count": 0,
        "group_counts": dict(sorted(group_counts.items())),
        "logger_scope_counts": dict(sorted(logger_scope_counts.items())),
        "safety": {
            "read_only": True,
            "app_source_modified": False,
            "cleanup_approved": False,
            "protected_words_used": PROTECTED_WORDS,
            "note": "This report narrows to logger fallback pass-only handlers only. It does not approve cleanup.",
        },
        "logger_fallback_sites": logger_sites,
        "recommendations": [
            "Do not apply cleanup from this report alone.",
            "Keep logger fallback behavior functionally unchanged.",
            "Only consider a future cleanup tool for exact reviewed logger fallback handlers.",
            "Do not touch business logic, reports, payments, balances, database, backups, or role/access handlers.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan logger fallback pass-only handler review.")
    parser.add_argument("--app", default=APP_FILE, help="Path to the SPINA app file.")
    parser.add_argument("--json", dest="json_path", help="Optional path to write JSON report.")
    parser.add_argument("--context-radius", type=int, default=8, help="Lines of context around each site.")
    args = parser.parse_args()

    report = build_report(Path(args.app), args.context_radius)
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.json_path:
        Path(args.json_path).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
