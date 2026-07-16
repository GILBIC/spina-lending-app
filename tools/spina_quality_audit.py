#!/usr/bin/env python3
"""Static quality audit for the SPINA desktop source file.

This tool is intentionally read-only. It does not import or run the Tkinter app.
It parses the Python source with ast and reports maintainability and reliability
hotspots that are useful before changing production behavior.
"""

from __future__ import annotations

import argparse
import ast
import collections
import json
from pathlib import Path
from typing import Any

PATCH_CLASSES = {"App", "LoanDB", "ClientsTab", "DataBankTab", "ReportsTab", "CollectorRouteTab"}
DEFAULT_LARGE_FUNCTION_LINES = 250

RISK_AREA_KEYWORDS = {
    "startup/database": (
        "startup", "init", "schema", "connect", "conn", "db", "database", "postgres", "pg_", "psycopg",
        "migrate", "ensure", "storage",
    ),
    "login/accounts": (
        "login", "auth", "account", "password", "user", "role", "session", "permission",
    ),
    "reports/pdf": (
        "report", "pdf", "statement", "ledger", "collector", "route", "receipt", "card", "print",
    ),
    "excel/import-export": (
        "excel", "xlsx", "import", "export", "template", "openpyxl", "spreadsheet",
    ),
    "backup/restore": (
        "backup", "restore", "dump", "pg_dump", "verify", "history",
    ),
    "payment/balance": (
        "payment", "balance", "interest", "principal", "advance", "adv", "pass", "renew",
    ),
}

VISIBLE_HANDLER_CALLS = {
    "print",
    "_spina_early_log",
    "_log_suppressed_once",
    "_spina_pg_storage_log",
    "_spina_perf_log",
    "logging.debug",
    "logging.info",
    "logging.warning",
    "logging.error",
    "logging.exception",
    "messagebox.showerror",
    "messagebox.showwarning",
    "messagebox.showinfo",
}


def _name(node: ast.AST | None) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return _name(node.func)
    return ""


def _line_span(node: ast.AST) -> int:
    end = getattr(node, "end_lineno", None) or getattr(node, "lineno", 0)
    start = getattr(node, "lineno", 0)
    return max(0, int(end) - int(start) + 1)


def _is_pass_only(nodes: list[ast.stmt]) -> bool:
    return bool(nodes) and all(isinstance(n, ast.Pass) for n in nodes)


def _sql_literal(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "f-string"
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        return "% formatting"
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format":
        return "format()"
    return None


def _risk_area(qualified_name: str) -> str:
    lowered = qualified_name.lower()
    for area, keywords in RISK_AREA_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return area
    return "general"


def _handler_has_visible_action(handler: ast.ExceptHandler) -> bool:
    for node in ast.walk(handler):
        if isinstance(node, (ast.Raise, ast.Assert)):
            return True
        if isinstance(node, ast.Call):
            call_name = _name(node.func)
            if call_name in VISIBLE_HANDLER_CALLS:
                return True
            if call_name.endswith((".error", ".exception", ".warning")):
                return True
    return False


def audit(path: Path, large_function_lines: int = DEFAULT_LARGE_FUNCTION_LINES) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))

    functions: dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]] = collections.defaultdict(list)
    class_methods: dict[str, dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]]] = collections.defaultdict(lambda: collections.defaultdict(list))
    repeated_assignments: dict[str, list[int]] = collections.defaultdict(list)
    large_functions: list[dict[str, Any]] = []
    broad_excepts: list[dict[str, Any]] = []
    pass_only_excepts: list[dict[str, Any]] = []
    bare_excepts: list[dict[str, Any]] = []
    silent_broad_excepts: list[dict[str, Any]] = []
    dynamic_sql: list[dict[str, Any]] = []
    psycopg_connect_calls: list[dict[str, Any]] = []
    possible_blocking_ui_calls: list[dict[str, Any]] = []

    class_stack: list[str] = []
    function_stack: list[str] = []

    class Visitor(ast.NodeVisitor):
        def visit_ClassDef(self, node: ast.ClassDef) -> Any:  # noqa: N802
            class_stack.append(node.name)
            for child in node.body:
                self.visit(child)
            class_stack.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:  # noqa: N802
            self._visit_function(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:  # noqa: N802
            self._visit_function(node)

        def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            span = _line_span(node)
            qualified = ".".join([*class_stack, node.name]) if class_stack else node.name
            if class_stack:
                class_methods[class_stack[-1]][node.name].append(node)
            else:
                functions[node.name].append(node)
            if span >= large_function_lines:
                large_functions.append({"name": qualified, "line": node.lineno, "lines": span})
            function_stack.append(qualified)
            try:
                for child in node.body:
                    self.visit(child)
            finally:
                function_stack.pop()

        def visit_Assign(self, node: ast.Assign) -> Any:  # noqa: N802
            for target in node.targets:
                self._record_assignment(target, node)
            self.generic_visit(node)

        def visit_AnnAssign(self, node: ast.AnnAssign) -> Any:  # noqa: N802
            self._record_assignment(node.target, node)
            self.generic_visit(node)

        def _record_assignment(self, target: ast.AST, node: ast.AST) -> None:
            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                if target.value.id in PATCH_CLASSES:
                    repeated_assignments[f"{target.value.id}.{target.attr}"].append(getattr(node, "lineno", 0))

        def visit_ExceptHandler(self, node: ast.ExceptHandler) -> Any:  # noqa: N802
            exc_type = _name(node.type) if node.type is not None else "bare"
            function_name = function_stack[-1] if function_stack else "<module>"
            item = {
                "line": node.lineno,
                "type": exc_type,
                "function": function_name,
                "risk_area": _risk_area(function_name),
                "visible_action": _handler_has_visible_action(node),
            }
            if node.type is None:
                bare_excepts.append(item)
            if exc_type in {"Exception", "BaseException", "bare"}:
                broad_excepts.append(item)
                if not item["visible_action"]:
                    silent_broad_excepts.append(item)
            if _is_pass_only(node.body):
                pass_only_excepts.append(item)
            self.generic_visit(node)

        def visit_Call(self, node: ast.Call) -> Any:  # noqa: N802
            call_name = _name(node.func)
            if call_name.endswith(".execute") and node.args:
                sql_kind = _sql_literal(node.args[0])
                if sql_kind in {"f-string", "% formatting", "format()"}:
                    dynamic_sql.append({"line": node.lineno, "kind": sql_kind})
                elif isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    text = node.args[0].value.lower()
                    if "{" in node.args[0].value or "}" in node.args[0].value:
                        dynamic_sql.append({"line": node.lineno, "kind": "template braces"})
                    elif any(word in text for word in ("select", "insert", "update", "delete", "create", "drop")) and "%" in node.args[0].value and len(node.args) == 1:
                        dynamic_sql.append({"line": node.lineno, "kind": "possible unbound % placeholder"})
            if call_name in {"psycopg.connect", "psycopg2.connect"} or call_name.endswith(".connect") and "psycopg" in call_name:
                psycopg_connect_calls.append({"line": node.lineno, "call": call_name})
            if call_name in {"time.sleep", "subprocess.run", "subprocess.call", "subprocess.check_output"}:
                possible_blocking_ui_calls.append({"line": node.lineno, "call": call_name})
            self.generic_visit(node)

    Visitor().visit(tree)

    duplicate_top_level = {
        name: [node.lineno for node in nodes]
        for name, nodes in sorted(functions.items())
        if len(nodes) > 1
    }
    duplicate_methods = {
        cls: {
            name: [node.lineno for node in nodes]
            for name, nodes in sorted(methods.items())
            if len(nodes) > 1
        }
        for cls, methods in sorted(class_methods.items())
    }
    duplicate_methods = {cls: methods for cls, methods in duplicate_methods.items() if methods}
    repeated_patch_targets = {
        name: lines for name, lines in sorted(repeated_assignments.items()) if len(lines) > 1
    }
    broad_except_by_risk_area = dict(
        sorted(collections.Counter(item["risk_area"] for item in broad_excepts).items())
    )
    silent_broad_except_by_risk_area = dict(
        sorted(collections.Counter(item["risk_area"] for item in silent_broad_excepts).items())
    )
    high_risk_silent_except_examples = [
        item for item in silent_broad_excepts if item["risk_area"] != "general"
    ][:50]

    return {
        "file": path.name,
        "line_count": source.count("\n") + 1,
        "top_level_function_count": sum(len(v) for v in functions.values()),
        "unique_top_level_function_names": len(functions),
        "duplicate_top_level_definitions": duplicate_top_level,
        "duplicate_class_methods": duplicate_methods,
        "repeated_patch_targets": repeated_patch_targets,
        "large_functions": sorted(large_functions, key=lambda item: item["lines"], reverse=True)[:50],
        "broad_except_count": len(broad_excepts),
        "pass_only_except_count": len(pass_only_excepts),
        "bare_except_count": len(bare_excepts),
        "silent_broad_except_count": len(silent_broad_excepts),
        "broad_except_by_risk_area": broad_except_by_risk_area,
        "silent_broad_except_by_risk_area": silent_broad_except_by_risk_area,
        "broad_except_examples": broad_excepts[:25],
        "pass_only_except_examples": pass_only_excepts[:25],
        "silent_broad_except_examples": silent_broad_excepts[:25],
        "high_risk_silent_except_examples": high_risk_silent_except_examples,
        "dynamic_sql_examples": dynamic_sql[:50],
        "dynamic_sql_count": len(dynamic_sql),
        "psycopg_connect_calls": psycopg_connect_calls,
        "possible_blocking_ui_calls": possible_blocking_ui_calls[:50],
    }


def print_report(report: dict[str, Any]) -> None:
    print(f"SPINA quality audit: {report['file']}")
    print(f"Lines: {report['line_count']}")
    print(f"Top-level functions: {report['top_level_function_count']} definitions / {report['unique_top_level_function_names']} unique names")
    print(f"Broad except handlers: {report['broad_except_count']}")
    print(f"Silent broad except handlers: {report['silent_broad_except_count']}")
    print(f"Pass-only except handlers: {report['pass_only_except_count']}")
    print(f"Bare except handlers: {report['bare_except_count']}")
    print(f"Dynamic SQL examples found: {report['dynamic_sql_count']}")

    print("\nSilent broad except handlers by risk area:")
    if report["silent_broad_except_by_risk_area"]:
        for area, count in report["silent_broad_except_by_risk_area"].items():
            print(f"  - {area}: {count}")
    else:
        print("  - none")

    print("\nLargest functions:")
    for item in report["large_functions"][:15]:
        print(f"  - {item['name']} at line {item['line']}: {item['lines']} lines")
    print("\nRepeated patch targets:")
    if report["repeated_patch_targets"]:
        for name, lines in list(report["repeated_patch_targets"].items())[:20]:
            print(f"  - {name}: {lines}")
    else:
        print("  - none")

    print("\nHigh-risk silent broad except examples:")
    if report["high_risk_silent_except_examples"]:
        for item in report["high_risk_silent_except_examples"][:15]:
            print(f"  - {item['risk_area']} {item['function']} at line {item['line']} ({item['type']})")
    else:
        print("  - none")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("python_file", type=Path)
    parser.add_argument("--json", dest="json_path", type=Path)
    parser.add_argument("--large-function-lines", type=int, default=DEFAULT_LARGE_FUNCTION_LINES)
    args = parser.parse_args()
    report = audit(args.python_file, args.large_function_lines)
    print_report(report)
    if args.json_path:
        args.json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
