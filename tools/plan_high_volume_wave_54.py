from __future__ import annotations

import ast
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
JSON_OUT = ROOT / "artifacts" / "wave-54-candidates.json"
MD_OUT = ROOT / "docs" / "wave-54-candidate-report.md"

MIN_LINES = 20
UI_CALL_TAILS = {
    "Button", "Label", "Frame", "Entry", "Treeview", "Scrollbar", "Combobox",
    "Checkbutton", "Radiobutton", "Notebook", "Toplevel", "Canvas", "Text",
    "pack", "grid", "place", "configure", "config", "bind", "heading", "column",
    "insert", "delete", "selection", "focus", "winfo_children", "winfo_exists",
    "StringVar", "BooleanVar", "IntVar", "DoubleVar", "after", "destroy",
}
PROTECTED_CALL_TAILS = {
    "connect_db", "run_write", "execute", "executemany", "commit", "rollback",
    "backup", "restore", "renew_client", "delete_transactions_for_day",
    "add_transaction", "update_transaction", "delete_transaction",
    "generate_client_pdf", "generate_pdf_selected", "print_full_daily_ledger",
    "print_collector_route_daily_ledger", "print_databank_close_report",
    "save_users", "set_password", "check_password", "authenticate",
}
FINANCIAL_IDENTIFIERS = {
    "principal", "interest", "balance", "remaining_balance", "loan_amount",
    "daily_amount", "payment_amount", "total_payment", "offset_amount",
    "renewal_amount", "due_date", "advance_days", "pass_days", "variance",
}
FILESYSTEM_CALL_TAILS = {
    "open", "write", "write_text", "write_bytes", "unlink", "mkdir", "makedirs",
    "remove", "rename", "replace", "copy", "copy2", "move", "startfile", "Popen",
    "run", "asksaveasfilename", "askopenfilename", "askdirectory",
}
SQL_RE = re.compile(r"\b(?:SELECT|INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|ALTER\s+TABLE|DROP\s+TABLE|CREATE\s+TABLE|WITH\s+\w+\s+AS)\b", re.I)


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def owner_name(stack: list[ast.AST], node: ast.AST) -> str:
    owners = [item.name for item in stack if isinstance(item, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))]
    return ".".join([*owners, node.name]) if owners else node.name


def identifier_names(node: ast.AST) -> set[str]:
    return {
        part.id.lower() for part in ast.walk(node) if isinstance(part, ast.Name)
    } | {
        part.attr.lower() for part in ast.walk(node) if isinstance(part, ast.Attribute)
    }


def financial_operation_hits(node: ast.AST) -> list[str]:
    hits: set[str] = set()
    operation_nodes = (ast.BinOp, ast.UnaryOp, ast.Compare, ast.IfExp, ast.AugAssign)
    for part in ast.walk(node):
        if isinstance(part, operation_nodes):
            hits.update(FINANCIAL_IDENTIFIERS & identifier_names(part))
    return sorted(hits)


def feature_group(name: str) -> str:
    low = name.lower()
    rules = (
        ("cash-control", ("cashctl", "cash_control", "cash_refresh")),
        ("data-bank", ("databank", "data_grid", "data_tab", "month", "cell_edit")),
        ("clients", ("client", "renewdialog")),
        ("collectors", ("collector", "route")),
        ("dashboard", ("dashboard", "dash_")),
        ("reports", ("report", "statement", "pdf")),
        ("authentication", ("login", "password", "account", "role", "permission", "user_header")),
        ("navigation-theme", ("nav", "header", "theme", "style", "palette")),
        ("areas", ("area",)),
        ("audit", ("audit",)),
        ("settings", ("setting",)),
        ("calendar", ("calendar", "date_picker")),
        ("notes", ("note",)),
    )
    for group, tokens in rules:
        if any(token in low for token in tokens):
            return group
    return "misc"


class Collector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.stack: list[ast.AST] = []
        self.functions: list[tuple[str, ast.AST, int]] = []
        self.name_refs: Counter[str] = Counter()
        self.attr_refs: Counter[str] = Counter()
        self.assignments: defaultdict[str, list[dict[str, object]]] = defaultdict(list)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.stack.append(node)
        self.generic_visit(node)
        self.stack.pop()

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        depth = sum(isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) for item in self.stack)
        self.functions.append((owner_name(self.stack, node), node, depth))
        self.stack.append(node)
        self.generic_visit(node)
        self.stack.pop()

    visit_FunctionDef = _visit_function
    visit_AsyncFunctionDef = _visit_function

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            self.name_refs[node.id] += 1
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.ctx, ast.Load):
            self.attr_refs[node.attr] += 1
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        rhs = ast.unparse(node.value)
        for target in node.targets:
            if isinstance(target, ast.Attribute):
                self.assignments[target.attr].append({"line": node.lineno, "rhs": rhs})
            elif isinstance(target, ast.Name):
                self.assignments[target.id].append({"line": node.lineno, "rhs": rhs})
        self.generic_visit(node)


def analyze_candidate(name: str, node: ast.AST, depth: int, collector: Collector) -> dict[str, object]:
    calls = sorted({dotted(part.func) for part in ast.walk(node) if isinstance(part, ast.Call) and dotted(part.func)})
    call_tails = {call.rsplit(".", 1)[-1] for call in calls}
    string_values = [
        part.value for part in ast.walk(node)
        if isinstance(part, ast.Constant) and isinstance(part.value, str)
    ]
    ui_hits = sorted(UI_CALL_TAILS & call_tails)
    protected_calls = sorted(PROTECTED_CALL_TAILS & call_tails)
    filesystem_calls = sorted(FILESYSTEM_CALL_TAILS & call_tails)
    financial_hits = financial_operation_hits(node)
    sql_hits = sorted({value.strip()[:120] for value in string_values if SQL_RE.search(value)})
    short_name = name.rsplit(".", 1)[-1]
    references = collector.name_refs[short_name] + collector.attr_refs[short_name]
    bindings = collector.assignments.get(short_name, [])
    lines = (getattr(node, "end_lineno", node.lineno) or node.lineno) - node.lineno + 1

    if depth > 0:
        classification = "nested"
    elif sql_hits or protected_calls or financial_hits:
        classification = "protected"
    elif filesystem_calls:
        classification = "filesystem-review"
    elif len(ui_hits) >= 3:
        classification = "ui-candidate"
    else:
        classification = "support-review"

    return {
        "qualified_name": name,
        "short_name": short_name,
        "feature_group": feature_group(name),
        "line_start": node.lineno,
        "line_end": getattr(node, "end_lineno", node.lineno),
        "lines": lines,
        "depth": depth,
        "classification": classification,
        "references": references,
        "bindings": bindings,
        "ui_hits": ui_hits,
        "protected_calls": protected_calls,
        "financial_hits": financial_hits,
        "filesystem_calls": filesystem_calls,
        "sql_hits": sql_hits,
        "calls": calls,
    }


def main() -> None:
    text = DESKTOP.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(DESKTOP))
    collector = Collector()
    collector.visit(tree)

    rows = []
    for name, node, depth in collector.functions:
        line_count = (getattr(node, "end_lineno", node.lineno) or node.lineno) - node.lineno + 1
        if line_count >= MIN_LINES:
            rows.append(analyze_candidate(name, node, depth, collector))

    rows.sort(key=lambda row: (row["classification"], -int(row["lines"]), row["qualified_name"]))
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    MD_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    safe = [row for row in rows if row["classification"] == "ui-candidate" and row["depth"] == 0]
    groups: defaultdict[str, list[dict[str, object]]] = defaultdict(list)
    for row in safe:
        groups[str(row["feature_group"])].append(row)
    group_rows = sorted(groups.items(), key=lambda item: -sum(int(row["lines"]) for row in item[1]))

    md = [
        "# Wave 54 high-volume candidate report",
        "",
        f"Scanned `{DESKTOP.name}` with a minimum size of {MIN_LINES} lines.",
        "",
        "Protection is based on actual calls, SQL-shaped strings, and financial arithmetic—not ordinary `pass` statements or visible UI labels.",
        "",
        "## Safe presentation groups",
        "",
        "| Group | Functions | Total lines | Largest members |",
        "|---|---:|---:|---|",
    ]
    for group, members in group_rows:
        total = sum(int(row["lines"]) for row in members)
        largest = sorted(members, key=lambda row: -int(row["lines"]))[:6]
        labels = ", ".join(f"`{row['qualified_name']}` ({row['lines']})" for row in largest)
        md.append(f"| {group} | {len(members)} | {total} | {labels} |")

    md.extend([
        "",
        "## Safe presentation candidates",
        "",
        "| Candidate | Group | Lines | Refs | UI evidence |",
        "|---|---|---:|---:|---|",
    ])
    for row in sorted(safe, key=lambda row: (row["feature_group"], -int(row["lines"])))[:100]:
        ui = ", ".join(row["ui_hits"][:8]) or "none"
        md.append(f"| `{row['qualified_name']}` | {row['feature_group']} | {row['lines']} | {row['references']} | {ui} |")

    md.extend([
        "",
        "## Protected large functions",
        "",
        "| Candidate | Lines | Protected evidence |",
        "|---|---:|---|",
    ])
    protected = [row for row in rows if row["classification"] == "protected" and row["depth"] == 0]
    protected.sort(key=lambda row: -int(row["lines"]))
    for row in protected[:35]:
        evidence = [*row["protected_calls"], *row["financial_hits"]]
        if row["sql_hits"]:
            evidence.append("SQL")
        md.append(f"| `{row['qualified_name']}` | {row['lines']} | {', '.join(evidence[:12]) or 'protected'} |")

    MD_OUT.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"Wrote {JSON_OUT.relative_to(ROOT)} and {MD_OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
