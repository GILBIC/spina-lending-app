from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
REPORT = ROOT / "artifacts" / "wave-53-planner.txt"

MIN_LINES = 100
SQL_RE = re.compile(r"\b(?:SELECT|INSERT|UPDATE|DELETE|ALTER|DROP|CREATE|REPLACE|PRAGMA)\b", re.I)

UI_PREFIXES = (
    "tk.", "ttk.", "messagebox.", "filedialog.", "simpledialog.", "colorchooser.",
)
UI_METHODS = {
    "pack", "grid", "place", "configure", "config", "bind", "heading", "column",
    "insert", "delete", "selection_set", "focus_set", "geometry", "transient",
    "grab_set", "wait_window", "protocol", "title", "resizable", "winfo_children",
    "tag_configure", "create_text", "create_rectangle", "create_line", "create_oval",
    "create_arc", "create_polygon", "yview", "xview", "set",
}
DB_TOKENS = {
    "connect_db", "cursor", "execute", "executemany", "commit", "rollback",
    "run_write", "fetchone", "fetchall", "fetchmany",
}
FILESYSTEM_TOKENS = {
    "open", "read_text", "write_text", "read_bytes", "write_bytes", "mkdir", "unlink",
    "rename", "replace", "copy", "copy2", "move", "rmtree", "startfile", "save",
    "Workbook", "load_workbook", "SimpleDocTemplate", "canvas.Canvas",
}
AUTH_TOKENS = {
    "verify_login", "hash_password", "set_user_password", "load_users_db", "save_users_db",
    "must_change_password", "apply_role_access", "switch_account",
}
FINANCIAL_TOKENS = {
    "principal", "interest", "balance", "renewal", "offset", "advance", "adv",
    "pass", "7x7", "due_date", "daily_amount", "loan_amount", "payment_term",
    "flex_due", "close_day", "delete_day",
}


@dataclass
class Candidate:
    owner: str
    name: str
    lineno: int
    end_lineno: int
    lines: int
    ui_calls: int
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


def source_text(text: str, node: ast.AST) -> str:
    return ast.get_source_segment(text, node) or ""


def analyze(owner: str, node: ast.FunctionDef | ast.AsyncFunctionDef, text: str, tree: ast.Module) -> Candidate:
    calls = node_calls(node)
    call_tails = {call.rsplit(".", 1)[-1] for call in calls}
    ui_calls = sum(
        1 for call in calls
        if call.startswith(UI_PREFIXES) or call.rsplit(".", 1)[-1] in UI_METHODS
    )
    src = source_text(text, node)
    src_lower = src.lower()
    names = {sub.id.lower() for sub in ast.walk(node) if isinstance(sub, ast.Name)}
    attrs = {sub.attr.lower() for sub in ast.walk(node) if isinstance(sub, ast.Attribute)}
    identifiers = names | attrs | {tail.lower() for tail in call_tails}

    reasons: list[str] = []
    if any(call.startswith("self.db") or call.startswith("db.") for call in calls):
        reasons.append("direct-db")
    if identifiers & {token.lower() for token in DB_TOKENS}:
        reasons.append("db-operation")
    if SQL_RE.search(src):
        reasons.append("sql-text")
    if identifiers & {token.lower() for token in FILESYSTEM_TOKENS}:
        reasons.append("filesystem/report-output")
    if identifiers & {token.lower() for token in AUTH_TOKENS}:
        reasons.append("authentication/access")

    financial_hits = sorted(token for token in FINANCIAL_TOKENS if token in src_lower)
    if financial_hits:
        reasons.append("protected-business:" + ",".join(financial_hits[:5]))

    assignments = assigned_targets(tree, node.name) if owner == "module" else ()
    lines = node.end_lineno - node.lineno + 1
    active_bonus = 80 if assignments or owner == "App" else 0
    danger_penalty = 250 * len(reasons)
    score = lines + ui_calls * 4 + active_bonus - danger_penalty
    return Candidate(
        owner=owner,
        name=node.name,
        lineno=node.lineno,
        end_lineno=node.end_lineno,
        lines=lines,
        ui_calls=ui_calls,
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
            lines = node.end_lineno - node.lineno + 1
            if lines >= MIN_LINES:
                candidates.append(analyze("module", node, text, tree))
        elif isinstance(node, ast.ClassDef) and node.name == "App":
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    lines = child.end_lineno - child.lineno + 1
                    if lines >= MIN_LINES:
                        candidates.append(analyze("App", child, text, tree))

    candidates.sort(key=lambda row: (not bool(row.reasons), row.score, row.lines), reverse=True)

    safe = [row for row in candidates if not row.reasons and row.ui_calls >= 8]
    review = [row for row in candidates if len(row.reasons) <= 1 and row.ui_calls >= 12]
    largest = sorted(candidates, key=lambda row: row.lines, reverse=True)[:25]

    rows: list[str] = []
    rows.append("WAVE 53 HIGH-VOLUME PLANNER")
    rows.append(f"Desktop file: {DESKTOP.name}")
    rows.append(f"Candidates >= {MIN_LINES} lines: {len(candidates)}")
    rows.append("")

    def emit(title: str, items: list[Candidate], limit: int = 20) -> None:
        rows.append(title)
        rows.append("=" * len(title))
        for row in items[:limit]:
            state = "SAFE" if not row.reasons else "REVIEW/REJECT"
            binding = ",".join(row.assignments) or "-"
            risk = ";".join(row.reasons) or "none"
            rows.append(
                f"{state:13} score={row.score:5} lines={row.lines:4} ui={row.ui_calls:3} "
                f"at={row.lineno}-{row.end_lineno} owner={row.owner:6} name={row.name} "
                f"bindings={binding} risk={risk}"
            )
        rows.append("")

    emit("SAFE UI-HEAVY CANDIDATES", safe, 30)
    emit("ONE-RISK REVIEW CANDIDATES", review, 30)
    emit("LARGEST FUNCTIONS FOR REJECTION REVIEW", largest, 30)

    report = "\n".join(rows) + "\n"
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
