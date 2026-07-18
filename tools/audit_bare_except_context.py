#!/usr/bin/env python3
"""Read-only audit for bare except blocks."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

DEFAULT_APP_FILE = "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"

PROTECTED_HINTS = (
    "payment", "balance", "7x7", "renew", "collector", "ledger",
    "statement", "report", "pdf", "backup", "restore", "postgres",
    "database", "migration", "transaction", "client", "cash", "login",
)

LOG_HINTS = ("_log", "logging", "traceback", "print(", "messagebox")


def _lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def _ctx(lines: list[str], line: int, radius: int) -> list[dict[str, Any]]:
    start = max(1, line - radius)
    end = min(len(lines), line + radius)
    return [{"line": i, "text": lines[i - 1]} for i in range(start, end + 1)]


def _count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for item in items:
        val = str(item.get(key, ""))
        out[val] = out.get(val, 0) + 1
    return dict(sorted(out.items()))


class Visitor(ast.NodeVisitor):
    def __init__(self, lines: list[str], radius: int) -> None:
        self.lines = lines
        self.radius = radius
        self.stack: list[str] = []
        self.sites: list[dict[str, Any]] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self.visit_FunctionDef(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> Any:
        if node.type is None:
            line = int(getattr(node, "lineno", 0) or 0)
            end_line = int(getattr(node, "end_lineno", line) or line)
            scope = ".".join(self.stack) if self.stack else "<module>"
            ctx = _ctx(self.lines, line, self.radius)
            text = (scope + "\n" + "\n".join(x["text"] for x in ctx)).lower()
            protected = any(h in text for h in PROTECTED_HINTS)
            body_text = "\n".join(
                self.lines[getattr(n, "lineno", line) - 1]
                for n in node.body[:8]
                if getattr(n, "lineno", 0)
            ).lower()
            pass_only = len(node.body) == 1 and isinstance(node.body[0], ast.Pass)
            has_log = any(h in body_text for h in LOG_HINTS)
            severity = "protected_review" if protected else "review_bare_except"
            self.sites.append({
                "line": line,
                "end_line": end_line,
                "scope": scope,
                "pass_only": pass_only,
                "has_logging_or_notice": has_log,
                "protected_context": protected,
                "severity": severity,
                "context": ctx,
            })
        self.generic_visit(node)


def build_report(path: Path, radius: int) -> dict[str, Any]:
    lines = _lines(path)
    tree = ast.parse("\n".join(lines), filename=str(path))
    visitor = Visitor(lines, radius)
    visitor.visit(tree)
    sites = visitor.sites
    return {
        "file": str(path),
        "line_count": len(lines),
        "context_radius": radius,
        "bare_except_count": len(sites),
        "protected_context_count": sum(1 for s in sites if s["protected_context"]),
        "non_protected_bare_except_count": sum(1 for s in sites if not s["protected_context"]),
        "pass_only_bare_except_count": sum(1 for s in sites if s["pass_only"]),
        "by_severity": _count_by(sites, "severity"),
        "sites": sites,
        "recommendations": [
            "Read-only audit only; no app source changes are made.",
            "Review each bare except in context before editing.",
            "Change only one narrow area at a time after a separate cleanup plan.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default=DEFAULT_APP_FILE)
    parser.add_argument("--json", dest="json_path")
    parser.add_argument("--context-radius", type=int, default=12)
    args = parser.parse_args()
    report = build_report(Path(args.file), max(1, args.context_radius))
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.json_path:
        Path(args.json_path).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
