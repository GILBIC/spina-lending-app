#!/usr/bin/env python3
"""Build a read-only module-separation map for the monolithic SPINA app.

The planner inspects top-level classes, functions, imports, globals, and coarse
feature dependencies. It never edits the application and never approves a move.
"""

from __future__ import annotations

import argparse
import ast
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

DEFAULT_APP = "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"

PROTECTED_WORDS = {
    "7x7", "7×7", "advance", "auth", "backup", "balance", "cash_control",
    "collector", "database", "interest", "ledger", "login", "migration",
    "payment", "payroll", "pdf", "postgres", "principal", "receipt",
    "renew", "report", "restore", "role", "statement", "transaction",
}

DEPENDENCY_PATTERNS: dict[str, tuple[str, ...]] = {
    "tkinter_ui": ("tk.", "ttk.", "messagebox", "filedialog", "toplevel", "canvas", "treeview"),
    "database": ("psycopg", "sqlite3", "cursor", "execute(", "executemany(", "commit(", "rollback("),
    "reports_pdf": ("reportlab", "canvas.", "simpledoc", "platypus", ".pdf", "pdfmetrics"),
    "filesystem_json": ("pathlib", "open(", "json.", "os.path", "shutil", "glob."),
    "threading_async": ("threading", "threadpool", "queue.", "after(", "future", "executor"),
    "process_shell": ("subprocess", "os.system", "popen", "shell=true"),
    "spreadsheet": ("openpyxl", "pandas", ".xlsx", ".xls"),
    "images": ("pil", "image.", "imagetk", ".png", ".jpg", ".jpeg"),
}

MODULE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("config/settings.py", ("config", "setting", "preference", "prefs", "app_dir", "path", "constant")),
    ("database/connection.py", ("connect", "connection", "cursor", "psycopg", "postgres", "sqlite")),
    ("database/backup_repository.py", ("backup", "restore", "dump", "pg_dump", "pg_restore")),
    ("database/clients_repository.py", ("client", "borrower", "person_uid")),
    ("database/payments_repository.py", ("payment", "transaction", "collection")),
    ("services/authentication_service.py", ("login", "password", "account", "role", "auth", "user")),
    ("services/loan_calculations.py", ("loan", "principal", "interest", "balance", "7x7", "7×7", "due_date")),
    ("services/renewal_service.py", ("renew", "renewal", "offset")),
    ("services/advance_pass_service.py", ("advance", "adv", "pass")),
    ("reports/client_statement.py", ("statement", "soa")),
    ("reports/daily_ledger.py", ("daily_ledger", "full_ledger", "ledger")),
    ("reports/collector_route.py", ("collector_route", "route_pdf")),
    ("reports/receipts.py", ("receipt",)),
    ("reports/payroll_reports.py", ("payroll", "payslip")),
    ("ui/dashboard_tab.py", ("dashboard",)),
    ("ui/clients_tab.py", ("clients_tab", "client_tab", "client_management")),
    ("ui/databank_tab.py", ("databank", "data_bank", "payment_grid")),
    ("ui/reports_tab.py", ("reports_tab", "report_center")),
    ("ui/collector_route_tab.py", ("collector_route_tab", "route_tab")),
    ("ui/payroll_tab.py", ("payroll_tab",)),
    ("ui/settings_tab.py", ("settings_tab", "maintenance")),
    ("utilities/logging.py", ("log", "logger", "trace", "diagnostic")),
    ("utilities/dates.py", ("date", "month", "calendar", "weekday")),
    ("utilities/file_storage.py", ("file", "json", "folder", "directory", "storage", "image")),
    ("utilities/tkinter_helpers.py", ("dialog", "window", "geometry", "focus", "cursor", "widget", "style")),
)


def _line_span(node: ast.AST) -> tuple[int, int, int]:
    start = int(getattr(node, "lineno", 0) or 0)
    end = int(getattr(node, "end_lineno", start) or start)
    return start, end, max(0, end - start + 1)


def _source_text(lines: list[str], node: ast.AST) -> str:
    start, end, _ = _line_span(node)
    if start <= 0 or end <= 0:
        return ""
    return "\n".join(lines[start - 1 : end]).lower()


def _loaded_names(node: ast.AST) -> set[str]:
    return {
        child.id
        for child in ast.walk(node)
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)
    }


def _called_names(node: ast.AST) -> set[str]:
    calls: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        if isinstance(child.func, ast.Name):
            calls.add(child.func.id)
        elif isinstance(child.func, ast.Attribute):
            calls.add(child.func.attr)
    return calls


def _dependency_signals(text: str) -> list[str]:
    return [name for name, patterns in DEPENDENCY_PATTERNS.items() if any(pattern in text for pattern in patterns)]


def _is_protected(name: str, text: str) -> bool:
    haystack = f"{name.lower()}\n{text}"
    return any(word in haystack for word in PROTECTED_WORDS)


def _suggest_module(name: str, kind: str, text: str, dependencies: Iterable[str]) -> str:
    haystack = f"{name.lower()}\n{text[:4000]}"
    for module, keywords in MODULE_RULES:
        if any(keyword in haystack for keyword in keywords):
            return module
    deps = set(dependencies)
    if kind == "class" and "tkinter_ui" in deps:
        return "ui/app_window.py"
    if "reports_pdf" in deps:
        return "reports/shared_pdf.py"
    if "database" in deps:
        return "database/repository_unclassified.py"
    if "tkinter_ui" in deps:
        return "utilities/tkinter_helpers.py"
    if "filesystem_json" in deps:
        return "utilities/file_storage.py"
    return "utilities/general.py"


def _risk_level(line_count: int, protected: bool, dependencies: Iterable[str], shared_globals: int) -> str:
    deps = set(dependencies)
    score = 4 if line_count >= 500 else 3 if line_count >= 250 else 2 if line_count >= 120 else 1 if line_count >= 60 else 0
    if protected:
        score += 4
    if "database" in deps:
        score += 2
    if "reports_pdf" in deps:
        score += 2
    if "tkinter_ui" in deps:
        score += 1
    score += 2 if shared_globals >= 10 else 1 if shared_globals >= 4 else 0
    return "high" if score >= 7 else "medium" if score >= 4 else "low"


def _top_level_assignments(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        targets: list[ast.AST] = []
        if isinstance(node, ast.Assign):
            targets.extend(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets.append(node.target)
        for target in targets:
            for child in ast.walk(target):
                if isinstance(child, ast.Name):
                    names.add(child.id)
    return names


def _imports(tree: ast.Module) -> list[str]:
    values: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            values.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            values.append(node.module)
    return sorted(set(values))


def _record_definition(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
    lines: list[str],
    global_assignments: set[str],
    top_level_definitions: set[str],
) -> dict[str, Any]:
    start, end, line_count = _line_span(node)
    text = _source_text(lines, node)
    dependencies = _dependency_signals(text)
    shared_globals = sorted((_loaded_names(node) & global_assignments) - {node.name})
    cross_calls = sorted((_called_names(node) & top_level_definitions) - {node.name})
    kind = "class" if isinstance(node, ast.ClassDef) else "function"
    protected = _is_protected(node.name, text)

    record: dict[str, Any] = {
        "name": node.name,
        "kind": kind,
        "line": start,
        "end_line": end,
        "line_count": line_count,
        "suggested_module": _suggest_module(node.name, kind, text, dependencies),
        "dependency_signals": dependencies,
        "protected_or_business_critical": protected,
        "shared_global_reads": shared_globals[:40],
        "shared_global_read_count": len(shared_globals),
        "cross_definition_calls": cross_calls[:40],
        "cross_definition_call_count": len(cross_calls),
        "move_risk": _risk_level(line_count, protected, dependencies, len(shared_globals)),
        "selected_for_move": False,
        "recommended_action": "Map and review only. This planner does not move production code.",
    }

    if isinstance(node, ast.ClassDef):
        methods = [child for child in node.body if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))]
        method_rows = []
        for method in methods:
            method_start, method_end, method_size = _line_span(method)
            method_rows.append({"name": method.name, "line": method_start, "end_line": method_end, "line_count": method_size})
        method_rows.sort(key=lambda item: (-int(item["line_count"]), str(item["name"])))
        record["method_count"] = len(methods)
        record["largest_methods"] = method_rows[:30]
    return record


def build_report(path: Path) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8", errors="replace")
    lines = source.splitlines()
    tree = ast.parse(source)
    definitions = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    global_assignments = _top_level_assignments(tree)
    definition_names = {node.name for node in definitions}
    records = [_record_definition(node, lines, global_assignments, definition_names) for node in definitions]
    records.sort(key=lambda item: int(item["line"]))

    module_counts = Counter(str(item["suggested_module"]) for item in records)
    risk_counts = Counter(str(item["move_risk"]) for item in records)
    dependency_counts = Counter(dep for item in records for dep in item["dependency_signals"])
    large_definitions = sorted(
        [item for item in records if int(item["line_count"]) >= 200],
        key=lambda item: (-int(item["line_count"]), str(item["name"])),
    )
    low_risk_candidates = [
        item for item in records
        if item["move_risk"] == "low"
        and not item["protected_or_business_critical"]
        and int(item["line_count"]) <= 120
        and str(item["suggested_module"]).startswith(("utilities/", "config/"))
        and "database" not in item["dependency_signals"]
        and "reports_pdf" not in item["dependency_signals"]
    ]
    low_risk_candidates.sort(key=lambda item: (
        int(item["shared_global_read_count"]),
        int(item["cross_definition_call_count"]),
        int(item["line_count"]),
        str(item["name"]),
    ))

    shared_usage: dict[str, list[str]] = defaultdict(list)
    for item in records:
        for name in item["shared_global_reads"]:
            shared_usage[name].append(str(item["name"]))
    hotspots = sorted(
        ({"name": name, "definition_user_count": len(users), "used_by": sorted(users)[:50]} for name, users in shared_usage.items()),
        key=lambda item: (-int(item["definition_user_count"]), str(item["name"])),
    )

    return {
        "file": str(path),
        "line_count": len(lines),
        "top_level_function_count": sum(1 for item in records if item["kind"] == "function"),
        "top_level_class_count": sum(1 for item in records if item["kind"] == "class"),
        "top_level_global_assignment_count": len(global_assignments),
        "imported_module_count": len(_imports(tree)),
        "imported_modules": _imports(tree),
        "selected_move_candidate_count": 0,
        "safety": {
            "read_only": True,
            "app_source_modified": False,
            "moves_approved": False,
            "note": "This report maps separation boundaries only. It does not move code.",
        },
        "summary": {
            "risk_counts": dict(risk_counts),
            "suggested_module_counts": dict(module_counts),
            "dependency_signal_counts": dict(dependency_counts),
            "definitions_at_least_200_lines": len(large_definitions),
            "definitions_at_least_500_lines": sum(1 for item in records if int(item["line_count"]) >= 500),
        },
        "recommended_first_wave_review": low_risk_candidates[:40],
        "large_definitions": large_definitions[:80],
        "global_dependency_hotspots": hotspots[:80],
        "definitions": records,
        "recommended_phases": [
            {"phase": 1, "name": "Utilities and configuration", "rule": "Only small low-risk helpers with no database, PDF, payment, balance, authentication, or Tkinter ownership dependencies."},
            {"phase": 2, "name": "Report generators", "rule": "Extract one report at a time and compare generated output before and after."},
            {"phase": 3, "name": "UI tabs", "rule": "Move one complete tab at a time while preserving callback signatures."},
            {"phase": 4, "name": "Business and database services", "rule": "Move only after calculation and database regression tests exist."},
        ],
        "next_action": "Review recommended_first_wave_review and choose one exact helper group for a guarded extraction PR. Do not batch-move unrelated functions.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app", nargs="?", default=DEFAULT_APP)
    parser.add_argument("--json", dest="json_path", help="Write the report to this JSON file")
    args = parser.parse_args()
    report = build_report(Path(args.app))
    payload = json.dumps(report, indent=2, ensure_ascii=False)
    if args.json_path:
        Path(args.json_path).write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
