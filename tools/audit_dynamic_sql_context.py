#!/usr/bin/env python3
"""Read-only audit for dynamic SQL execution sites in the SPINA app.

This tool does not edit source files. It finds execute/executemany calls whose
SQL argument is not a plain string literal, then emits context so each site can
be reviewed before any behavior changes are considered.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
from pathlib import Path
from typing import Any

DEFAULT_APP = "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"

EXECUTE_METHODS = {"execute", "executemany", "executescript"}
PROTECTED_TERMS = {
    "balance", "7x7", "interest", "principal", "payment", "payments",
    "transaction", "transactions", "collector", "collectors", "route",
    "ledger", "statement", "report", "reports", "pdf", "renew", "renewal",
    "cash", "cash-control", "migration", "migrate", "backup", "restore",
    "postgres", "postgresql", "database", "client", "clients", "loan",
    "loans", "note", "notes", "advance", "adv", "pass",
}


def node_kind(node: ast.AST | None) -> str:
    if node is None:
        return "none"
    if isinstance(node, ast.Constant):
        return "constant"
    if isinstance(node, ast.JoinedStr):
        return "f_string"
    if isinstance(node, ast.BinOp):
        return "bin_op"
    if isinstance(node, ast.Name):
        return "name"
    if isinstance(node, ast.Call):
        return "call"
    if isinstance(node, ast.Attribute):
        return "attribute"
    if isinstance(node, ast.Subscript):
        return "subscript"
    return type(node).__name__


def safe_unparse(node: ast.AST | None) -> str:
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:
        return type(node).__name__


def is_plain_sql_literal(node: ast.AST | None) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def call_name(node: ast.AST) -> tuple[str, str]:
    if isinstance(node, ast.Attribute):
        return node.attr, safe_unparse(node)
    if isinstance(node, ast.Name):
        return node.id, node.id
    return "", safe_unparse(node)


def enclosing_stack(tree: ast.AST) -> dict[int, list[dict[str, Any]]]:
    stack_by_id: dict[int, list[dict[str, Any]]] = {}
    stack: list[dict[str, Any]] = []

    class Visitor(ast.NodeVisitor):
        def generic_visit(self, node: ast.AST) -> Any:
            stack_by_id[id(node)] = list(stack)
            super().generic_visit(node)

        def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
            stack_by_id[id(node)] = list(stack)
            item = {
                "type": "function",
                "name": node.name,
                "line": getattr(node, "lineno", None),
                "end_line": getattr(node, "end_lineno", None),
            }
            stack.append(item)
            self.generic_visit(node)
            stack.pop()

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
            self.visit_FunctionDef(node)  # type: ignore[arg-type]

        def visit_ClassDef(self, node: ast.ClassDef) -> Any:
            stack_by_id[id(node)] = list(stack)
            item = {
                "type": "class",
                "name": node.name,
                "line": getattr(node, "lineno", None),
                "end_line": getattr(node, "end_lineno", None),
            }
            stack.append(item)
            self.generic_visit(node)
            stack.pop()

    Visitor().visit(tree)
    return stack_by_id


def qualname(stack: list[dict[str, Any]]) -> str:
    names = [str(x.get("name")) for x in stack if x.get("name")]
    return ".".join(names) if names else "<module>"


def context(lines: list[str], line: int, end_line: int | None = None, radius: int = 8) -> list[dict[str, Any]]:
    if end_line is None:
        end_line = line
    start = max(1, line - radius)
    stop = min(len(lines), end_line + radius)
    return [
        {"line": i, "text": lines[i - 1].rstrip("\n")}
        for i in range(start, stop + 1)
    ]


def has_protected_context(lines: list[str], line: int, end_line: int | None = None, radius: int = 12) -> bool:
    if end_line is None:
        end_line = line
    start = max(1, line - radius)
    stop = min(len(lines), end_line + radius)
    text = "\n".join(lines[start - 1:stop]).lower()
    return any(term in text for term in PROTECTED_TERMS)


def classify_risk(kind: str, protected: bool, sql_preview: str) -> str:
    low_preview = sql_preview.lower()
    if protected:
        return "protected_review"
    if kind in {"f_string", "bin_op"}:
        return "review_dynamic_sql"
    if any(word in low_preview for word in ("format", "join", "%")):
        return "review_dynamic_sql"
    return "review_variable_sql"


def audit(path: Path, radius: int) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(True)
    tree = ast.parse(text, filename=str(path))
    stacks = enclosing_stack(tree)
    sites: list[dict[str, Any]] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        method, func_text = call_name(node.func)
        if method not in EXECUTE_METHODS:
            continue
        sql_arg = node.args[0] if node.args else None
        if is_plain_sql_literal(sql_arg):
            continue
        line = getattr(node, "lineno", None)
        if not line:
            continue
        end_line = getattr(node, "end_lineno", line)
        stack = stacks.get(id(node), [])
        kind = node_kind(sql_arg)
        preview = safe_unparse(sql_arg)
        protected = has_protected_context(lines, line, end_line, radius=12)
        sites.append({
            "line": line,
            "end_line": end_line,
            "method": method,
            "function_text": func_text,
            "sql_arg_kind": kind,
            "sql_arg_preview": preview[:240],
            "caller": qualname(stack),
            "protected_context": protected,
            "severity": classify_risk(kind, protected, preview),
            "context": context(lines, line, end_line, radius=radius),
        })

    protected_count = sum(1 for s in sites if s["protected_context"])
    by_kind: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for site in sites:
        by_kind[site["sql_arg_kind"]] = by_kind.get(site["sql_arg_kind"], 0) + 1
        by_severity[site["severity"]] = by_severity.get(site["severity"], 0) + 1

    return {
        "file": str(path),
        "line_count": len(lines),
        "dynamic_sql_call_count": len(sites),
        "protected_context_count": protected_count,
        "non_protected_dynamic_sql_count": len(sites) - protected_count,
        "by_sql_arg_kind": by_kind,
        "by_severity": by_severity,
        "sites": sites,
        "recommendations": [
            "Read-only dynamic SQL context audit only; no app source changes are made.",
            "Do not edit protected database/payment/report/collector/backup paths from this audit alone.",
            "Review non-protected dynamic SQL one call family at a time before changing behavior.",
            "Prefer replacing dynamic table or column names with explicit whitelists, not string concatenation, when a change is approved.",
            "After any approved change, run py_compile and smoke-test login, clients, payments, reports, backups, and collector routes.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit dynamic SQL execution sites in the SPINA app.")
    parser.add_argument("app", nargs="?", default=DEFAULT_APP)
    parser.add_argument("--json", dest="json_path", default=None)
    parser.add_argument("--context-radius", type=int, default=8)
    args = parser.parse_args()

    path = Path(args.app)
    if not path.exists():
        raise SystemExit(f"App file not found: {path}")

    result = audit(path, radius=max(0, args.context_radius))
    data = json.dumps(result, indent=2, ensure_ascii=False)
    if args.json_path:
        out = Path(args.json_path)
        out.write_text(data + "\n", encoding="utf-8")
        print(f"Wrote {out}")
    else:
        print(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
