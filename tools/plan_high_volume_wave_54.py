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

MIN_LINES = 90
UI_CALL_TAILS = {
    "Button", "Label", "Frame", "Entry", "Treeview", "Scrollbar", "Combobox",
    "Checkbutton", "Radiobutton", "Notebook", "Toplevel", "Canvas", "Text",
    "pack", "grid", "place", "configure", "config", "bind", "heading", "column",
    "insert", "delete", "selection", "focus", "winfo_children", "winfo_exists",
    "StringVar", "BooleanVar", "IntVar", "DoubleVar", "after", "destroy",
}
PROTECTED_TERMS = {
    "principal", "interest", "balance", "renew", "reloan", "offset", "payment",
    "transaction", "advance", "adv", "pass", "7x7", "due_date", "daily_amount",
    "loan_amount", "collector_route_daily_ledger", "full_daily_ledger", "statement",
    "report", "pdf", "backup", "restore", "postgres", "sqlite", "connect_db",
    "run_write", "execute", "executemany", "commit", "rollback", "authentication",
    "password", "login", "role", "permission", "users_json", "day_close",
    "close_day", "reopen", "cash_control", "payroll", "sss", "philhealth", "pagibig",
}
FILESYSTEM_TERMS = {
    "open", "write", "write_text", "write_bytes", "unlink", "mkdir", "makedirs",
    "remove", "rename", "replace", "copy", "copy2", "move", "startfile", "subprocess",
    "filedialog", "asksaveasfilename", "askopenfilename", "path", "os.path",
}
SQL_RE = re.compile(r"\b(?:SELECT|INSERT|UPDATE|DELETE|ALTER|DROP|CREATE|WITH)\b", re.I)


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def source_for(lines: list[str], node: ast.AST) -> str:
    end = getattr(node, "end_lineno", None) or node.lineno
    return "\n".join(lines[node.lineno - 1 : end])


def owner_name(stack: list[ast.AST], node: ast.AST) -> str:
    owners = [item.name for item in stack if isinstance(item, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))]
    return ".".join([*owners, node.name]) if owners else node.name


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


def analyze_candidate(name: str, node: ast.AST, depth: int, source: str, collector: Collector) -> dict[str, object]:
    calls = sorted({dotted(part.func) for part in ast.walk(node) if isinstance(part, ast.Call) and dotted(part.func)})
    call_tails = {call.rsplit(".", 1)[-1] for call in calls}
    identifiers = {
        part.id.lower() for part in ast.walk(node) if isinstance(part, ast.Name)
    } | {
        part.attr.lower() for part in ast.walk(node) if isinstance(part, ast.Attribute)
    }
    string_values = [
        part.value for part in ast.walk(node)
        if isinstance(part, ast.Constant) and isinstance(part.value, str)
    ]
    source_lower = source.lower()
    ui_hits = sorted(UI_CALL_TAILS & call_tails)
    protected_hits = sorted(term for term in PROTECTED_TERMS if term in identifiers or term in source_lower)
    filesystem_hits = sorted(term for term in FILESYSTEM_TERMS if term in identifiers or term in source_lower)
    sql_hits = sorted({value.strip()[:120] for value in string_values if SQL_RE.search(value)})
    short_name = name.rsplit(".", 1)[-1]
    references = collector.name_refs[short_name] + collector.attr_refs[short_name]
    bindings = collector.assignments.get(short_name, [])
    lines = (getattr(node, "end_lineno", node.lineno) or node.lineno) - node.lineno + 1

    if depth > 0:
        classification = "nested"
    elif protected_hits or sql_hits:
        classification = "protected"
    elif filesystem_hits:
        classification = "filesystem-review"
    elif len(ui_hits) >= 3:
        classification = "ui-candidate"
    else:
        classification = "support-review"

    legacy_score = 0
    if references <= 1:
        legacy_score += 3
    if not bindings:
        legacy_score += 2
    if any(token in short_name.lower() for token in ("legacy", "old", "v1", "v2", "v3", "unused")):
        legacy_score += 2
    if classification == "ui-candidate":
        legacy_score += 2

    return {
        "qualified_name": name,
        "short_name": short_name,
        "line_start": node.lineno,
        "line_end": getattr(node, "end_lineno", node.lineno),
        "lines": lines,
        "depth": depth,
        "classification": classification,
        "references": references,
        "bindings": bindings,
        "ui_hits": ui_hits,
        "protected_hits": protected_hits,
        "filesystem_hits": filesystem_hits,
        "sql_hits": sql_hits,
        "calls": calls,
        "legacy_score": legacy_score,
    }


def main() -> None:
    text = DESKTOP.read_text(encoding="utf-8")
    lines = text.splitlines()
    tree = ast.parse(text, filename=str(DESKTOP))
    collector = Collector()
    collector.visit(tree)

    rows = []
    for name, node, depth in collector.functions:
        line_count = (getattr(node, "end_lineno", node.lineno) or node.lineno) - node.lineno + 1
        if line_count < MIN_LINES:
            continue
        rows.append(analyze_candidate(name, node, depth, source_for(lines, node), collector))

    rows.sort(key=lambda row: (
        0 if row["classification"] == "ui-candidate" else 1,
        -int(row["legacy_score"]),
        -int(row["lines"]),
    ))
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    MD_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    selected = [row for row in rows if row["classification"] in {"ui-candidate", "filesystem-review", "support-review"} and row["depth"] == 0]
    md = [
        "# Wave 54 high-volume candidate report",
        "",
        f"Scanned `{DESKTOP.name}` with a minimum size of {MIN_LINES} lines.",
        "",
        "The planner is intentionally conservative. `protected` candidates are excluded from Wave 54 even when their architecture-map risk looks UI-heavy.",
        "",
        "| Rank | Candidate | Lines | Class | Refs | Bindings | UI evidence | Review flags |",
        "|---:|---|---:|---|---:|---:|---|---|",
    ]
    for index, row in enumerate(selected[:35], start=1):
        flags = ", ".join(row["filesystem_hits"][:6]) or "none"
        ui = ", ".join(row["ui_hits"][:8]) or "none"
        md.append(
            f"| {index} | `{row['qualified_name']}` | {row['lines']} | {row['classification']} | "
            f"{row['references']} | {len(row['bindings'])} | {ui} | {flags} |"
        )
    md.extend([
        "",
        "## Protected large functions",
        "",
        "| Candidate | Lines | Protected evidence |",
        "|---|---:|---|",
    ])
    protected = [row for row in rows if row["classification"] == "protected" and row["depth"] == 0]
    protected.sort(key=lambda row: -int(row["lines"]))
    for row in protected[:25]:
        evidence = ", ".join(row["protected_hits"][:10]) or "SQL string"
        md.append(f"| `{row['qualified_name']}` | {row['lines']} | {evidence} |")

    MD_OUT.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"Wrote {JSON_OUT.relative_to(ROOT)} and {MD_OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
