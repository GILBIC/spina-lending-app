from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
REPORT = ROOT / "artifacts" / "wave-53-planner.txt"

MIN_LINES = 90
SQL_SHAPE_RE = re.compile(
    r"(?:\bSELECT\b[\s\S]{0,120}\bFROM\b|\bINSERT\s+INTO\b|\bUPDATE\b[\s\S]{0,80}\bSET\b|"
    r"\bDELETE\s+FROM\b|\bALTER\s+TABLE\b|\bDROP\s+TABLE\b|\bCREATE\s+TABLE\b|"
    r"\bREPLACE\s+INTO\b|\bPRAGMA\b)",
    re.I,
)

UI_PREFIXES = (
    "tk.", "ttk.", "messagebox.", "filedialog.", "simpledialog.", "colorchooser.",
)
UI_METHODS = {
    "pack", "grid", "place", "configure", "config", "bind", "heading", "column",
    "insert", "delete", "selection_set", "focus_set", "geometry", "transient",
    "grab_set", "wait_window", "protocol", "title", "resizable", "winfo_children",
    "tag_configure", "create_text", "create_rectangle", "create_line", "create_oval",
    "create_arc", "create_polygon", "yview", "xview", "set", "lift", "lower",
}
DB_CALL_TAILS = {
    "connect_db", "cursor", "execute", "executemany", "commit", "rollback",
    "run_write", "fetchone", "fetchall", "fetchmany",
}
FILESYSTEM_CALLS = {
    "open", "Path", "Workbook", "load_workbook", "SimpleDocTemplate", "canvas.Canvas",
    "os.startfile", "shutil.copy", "shutil.copy2", "shutil.move", "shutil.rmtree",
}
FILESYSTEM_TAILS = {
    "read_text", "write_text", "read_bytes", "write_bytes", "mkdir", "unlink",
    "rename", "replace", "copy", "copy2", "move", "rmtree", "startfile",
    "asksaveasfilename", "askopenfilename", "askdirectory",
}
AUTH_IDENTIFIERS = {
    "verify_login", "hash_password", "set_user_password", "load_users_db", "save_users_db",
    "must_change_password", "apply_role_access", "switch_account", "current_user_role",
    "access_profile", "permission_profile",
}
FINANCIAL_IDENTIFIERS = {
    "principal", "interest", "interest_rate", "interest_amount", "balance", "renewal",
    "offset", "advance", "adv", "due_date", "daily_amount", "loan_amount",
    "payment_term", "flex_due", "flex_due_rule", "close_day", "delete_day",
    "total_to_pay", "remaining_balance", "pay_start_offset_days",
}


@dataclass
class Candidate:
    owner: str
    name: str
    lineno: int
    end_lineno: int
    lines: int
    ui_calls: int
    external_loads: int
    assignments: tuple[str, ...]
    reasons: tuple[str, ...]
    score: int


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def node_calls(node: ast.AST) -> list[str]:
    out: list[str] = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            name = dotted(sub.func)
            if name:
                out.append(name)
    return out


def assigned_targets(tree: ast.Module, function_name: str) -> tuple[str, ...]:
    targets: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Name):
            continue
        if node.value.id != function_name:
            continue
        for target in node.targets:
            rendered = dotted(target)
            if rendered:
                targets.append(rendered)
    return tuple(sorted(set(targets)))


def external_load_count(tree: ast.Module, function_node: ast.AST, function_name: str) -> int:
    count = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Name) or not isinstance(node.ctx, ast.Load) or node.id != function_name:
            continue
        if getattr(function_node, "lineno", 0) <= getattr(node, "lineno", 0) <= getattr(function_node, "end_lineno", 0):
            continue
        count += 1
    return count


def sql_strings(node: ast.AST) -> list[str]:
    hits: list[str] = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str) and SQL_SHAPE_RE.search(sub.value):
            hits.append(sub.value[:120].replace("\n", " "))
    return hits


def analyze(owner: str, node: ast.FunctionDef | ast.AsyncFunctionDef, tree: ast.Module) -> Candidate:
    calls = node_calls(node)
    tails = {call.rsplit(".", 1)[-1] for call in calls}
    ui_calls = sum(
        1 for call in calls
        if call.startswith(UI_PREFIXES) or call.rsplit(".", 1)[-1] in UI_METHODS
    )
    names = {sub.id.lower() for sub in ast.walk(node) if isinstance(sub, ast.Name)}
    attrs = {sub.attr.lower() for sub in ast.walk(node) if isinstance(sub, ast.Attribute)}
    identifiers = names | attrs | {tail.lower() for tail in tails}

    reasons: list[str] = []
    if any(call.startswith("self.db") or call.startswith("db.") for call in calls):
        reasons.append("direct-db")
    if {tail.lower() for tail in tails} & {token.lower() for token in DB_CALL_TAILS}:
        reasons.append("db-operation")
    if sql_strings(node):
        reasons.append("sql-string")
    if any(call in FILESYSTEM_CALLS for call in calls) or (
        {tail.lower() for tail in tails} & {token.lower() for token in FILESYSTEM_TAILS}
    ):
        reasons.append("filesystem/report-output")
    if identifiers & {token.lower() for token in AUTH_IDENTIFIERS}:
        reasons.append("authentication/access")

    financial_hits = sorted(
        token for token in FINANCIAL_IDENTIFIERS if token.lower() in identifiers
    )
    if financial_hits:
        reasons.append("protected-business:" + ",".join(financial_hits[:6]))

    assignments = assigned_targets(tree, node.name) if owner == "module" else ()
    loads = external_load_count(tree, node, node.name) if owner == "module" else 0
    lines = node.end_lineno - node.lineno + 1
    active_bonus = 100 if owner == "App" or assignments or loads else 0
    inactive_penalty = 180 if owner == "module" and not assignments and not loads else 0
    danger_penalty = 320 * len(reasons)
    score = lines + ui_calls * 4 + active_bonus - inactive_penalty - danger_penalty
    return Candidate(
        owner=owner,
        name=node.name,
        lineno=node.lineno,
        end_lineno=node.end_lineno,
        lines=lines,
        ui_calls=ui_calls,
        external_loads=loads,
        assignments=assignments,
        reasons=tuple(reasons),
        score=score,
    )


def main() -> None:
    text = DESKTOP.read_text(encoding="utf-8")
    tree = ast.parse(text)
    candidates: list[Candidate] = []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.end_lineno - node.lineno + 1 >= MIN_LINES:
                candidates.append(analyze("module", node, tree))
        elif isinstance(node, ast.ClassDef) and node.name == "App":
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if child.end_lineno - child.lineno + 1 >= MIN_LINES:
                        candidates.append(analyze("App", child, tree))

    candidates.sort(key=lambda row: (not row.reasons, row.score, row.lines), reverse=True)

    safe_active = [
        row for row in candidates
        if not row.reasons
        and row.ui_calls >= 8
        and (row.owner == "App" or row.assignments or row.external_loads)
    ]
    safe_inactive = [
        row for row in candidates
        if not row.reasons
        and row.ui_calls >= 8
        and row.owner == "module"
        and not row.assignments
        and not row.external_loads
    ]
    review = [row for row in candidates if len(row.reasons) == 1 and row.ui_calls >= 12]
    largest = sorted(candidates, key=lambda row: row.lines, reverse=True)[:30]

    rows: list[str] = []
    rows.append("WAVE 53 HIGH-VOLUME PLANNER")
    rows.append(f"Desktop file: {DESKTOP.name}")
    rows.append(f"Candidates >= {MIN_LINES} lines: {len(candidates)}")
    rows.append("")

    def emit(title: str, items: list[Candidate], limit: int = 30) -> None:
        rows.append(title)
        rows.append("=" * len(title))
        for row in items[:limit]:
            state = "SAFE" if not row.reasons else "REVIEW"
            binding = ",".join(row.assignments) or "-"
            risk = ";".join(row.reasons) or "none"
            rows.append(
                f"{state:7} score={row.score:5} lines={row.lines:4} ui={row.ui_calls:3} "
                f"loads={row.external_loads:2} at={row.lineno}-{row.end_lineno} "
                f"owner={row.owner:6} name={row.name} bindings={binding} risk={risk}"
            )
        rows.append("")

    emit("SAFE ACTIVE UI-HEAVY CANDIDATES", safe_active)
    emit("SAFE BUT APPARENTLY INACTIVE CANDIDATES", safe_inactive)
    emit("ONE-RISK MANUAL REVIEW CANDIDATES", review)
    emit("LARGEST FUNCTIONS FOR REJECTION REVIEW", largest)

    report = "\n".join(rows) + "\n"
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
