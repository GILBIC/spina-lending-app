from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
OUT = ROOT / "artifacts" / "wave-51-high-volume-plan.json"

MIN_LINES = 150
MAX_LINES = 450
MIN_FUNCS = 2
MAX_FUNCS = 12
MAX_GAP = 45

FORBIDDEN_TOKENS = (
    # Database / persistence
    "connect_db(", "run_write(", ".execute(", ".executemany(", ".commit(",
    ".rollback(", "cursor(", "insert into", "delete from", "alter table",
    "create table", "drop table", "pragma ", "self.db", "psycopg", "sqlite3",
    # Filesystem / imports / exports / reports
    "open(", "pathlib", "path(", ".read_text(", ".write_text(", ".read_bytes(",
    ".write_bytes(", "json.load", "json.dump", "os.remove", "os.rename",
    "os.replace", "os.makedirs", "shutil.", "subprocess.", "filedialog",
    "reportlab", "canvas(", "pdf", "export", "import", "backup", "restore",
    "print_", "printer", "workbook", "openpyxl", "csv.",
    # Authentication / permissions
    "password", "verify_login", "authenticate", "permission", "role", "users_db",
    "account_choices", "must_change_password", "hash_password",
    # Lending / operational behavior
    "principal", "interest", "balance", "payment", "renewal", "offset", "advance",
    "\"adv", "'adv", " pass", "7x7", "due_date", "loan_type", "daily_amount",
    "auto_close", "close_day", "day_close", "schedule", ".after(", ".after_idle(",
    # Mutation / destructive operations
    "save_", "delete_", "remove_", "update_", "insert_", "create_", "add_",
    "edit_", "write_", "apply_", "set_password", "mark_", "approve_", "reject_",
    "archive_", "trash_", "upload_", "download_", "migrate_",
    # Threads / external side effects
    "threading.", "thread(", "socket", "requests.", "urllib", "webbrowser",
)

NAME_FORBIDDEN = re.compile(
    r"(?:payment|balance|principal|interest|renew|offset|advance|pass|7x7|loan|due|"
    r"auth|login|password|permission|role|report|pdf|print|export|import|backup|"
    r"restore|save|delete|remove|update|insert|create|add|edit|write|apply|mark|"
    r"approve|reject|archive|upload|download|migrate|close_day|auto_close|schedule)",
    re.I,
)

UI_MARKERS = (
    "tk.", "ttk.", ".pack(", ".grid(", ".place(", ".configure(", ".config(",
    ".bind(", ".heading(", ".column(", ".tag_configure(", "StringVar(",
    "BooleanVar(", "IntVar(", "DoubleVar(", "messagebox.", "font=(", "bg=", "fg=",
)

ALLOWED_CALL_PREFIXES = (
    "tk.", "ttk.", "messagebox.", "str", "int", "float", "bool", "len", "list",
    "tuple", "dict", "set", "sorted", "enumerate", "range", "min", "max", "sum",
    "getattr", "hasattr", "isinstance", "callable", "abs", "round", "zip", "map",
)


def normalized(source: str) -> str:
    return "\n".join(line.rstrip() for line in source.strip().splitlines()) + "\n"


def source_hash(source: str) -> str:
    return hashlib.sha256(normalized(source).encode("utf-8")).hexdigest()


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def family(name: str) -> str:
    cleaned = re.sub(r"^_+", "", name)
    parts = cleaned.split("_")
    if len(parts) >= 3 and parts[0] == "spina" and re.fullmatch(r"v\d+", parts[1]):
        return "_".join(parts[:3])
    return "_".join(parts[:2]) if len(parts) >= 2 else cleaned


def inspect_function(text: str, node: ast.FunctionDef) -> dict[str, object]:
    source = ast.get_source_segment(text, node) or ""
    lower = source.lower()
    calls = sorted({
        dotted(call.func)
        for call in ast.walk(node)
        if isinstance(call, ast.Call) and dotted(call.func)
    })
    forbidden_hits = sorted({token for token in FORBIDDEN_TOKENS if token.lower() in lower})
    ui_hits = sum(source.count(marker) for marker in UI_MARKERS)
    self_calls = sorted(call for call in calls if call.startswith("self."))
    external_calls = sorted(
        call for call in calls
        if not call.startswith(ALLOWED_CALL_PREFIXES)
        and not call.startswith(("self.", "super.", "w.", "widget.", "tree.", "style.", "st.", "btn.", "lbl.", "frm.", "frame.", "box.", "row.", "col.", "menu.", "canvas."))
    )
    safe = (
        not NAME_FORBIDDEN.search(node.name)
        and not forbidden_hits
        and ui_hits >= 3
        and len(source.splitlines()) >= 8
    )
    return {
        "name": node.name,
        "family": family(node.name),
        "lineno": node.lineno,
        "end_lineno": node.end_lineno,
        "lines": (node.end_lineno or node.lineno) - node.lineno + 1,
        "signature": ast.unparse(node.args),
        "sha256": source_hash(source),
        "ui_hits": ui_hits,
        "calls": calls,
        "self_calls": self_calls,
        "external_calls": external_calls,
        "forbidden_hits": forbidden_hits,
        "safe": safe,
        "first_line": source.splitlines()[0] if source else "",
    }


def main() -> None:
    text = DESKTOP.read_text(encoding="utf-8")
    tree = ast.parse(text)
    records = [
        inspect_function(text, node)
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    ]

    safe_records = [record for record in records if record["safe"]]
    safe_records.sort(key=lambda item: int(item["lineno"]))

    batches: list[dict[str, object]] = []
    for start in range(len(safe_records)):
        total = 0
        current: list[dict[str, object]] = []
        previous_end = None
        for stop in range(start, min(len(safe_records), start + MAX_FUNCS)):
            record = safe_records[stop]
            if previous_end is not None:
                gap = int(record["lineno"]) - int(previous_end) - 1
                if gap > MAX_GAP:
                    break
            current.append(record)
            total += int(record["lines"])
            previous_end = record["end_lineno"]
            if total > MAX_LINES:
                break
            if len(current) < MIN_FUNCS or total < MIN_LINES:
                continue

            families = {str(item["family"]) for item in current}
            family_bonus = 80 if len(families) == 1 else 35 if len(families) == 2 else 0
            compact_span = int(current[-1]["end_lineno"]) - int(current[0]["lineno"]) + 1
            gap_lines = compact_span - total
            ui_hits = sum(int(item["ui_hits"]) for item in current)
            external_count = sum(len(item["external_calls"]) for item in current)
            score = total * 3 + ui_hits * 2 + family_bonus - gap_lines * 2 - external_count * 3
            batches.append({
                "score": score,
                "function_count": len(current),
                "total_lines": total,
                "span_lines": compact_span,
                "gap_lines": gap_lines,
                "families": sorted(families),
                "start_line": current[0]["lineno"],
                "end_line": current[-1]["end_lineno"],
                "functions": current,
            })

    unique: dict[tuple[str, ...], dict[str, object]] = {}
    for batch in sorted(batches, key=lambda item: (-int(item["score"]), -int(item["total_lines"]))):
        key = tuple(str(item["name"]) for item in batch["functions"])
        unique.setdefault(key, batch)

    ranked = list(unique.values())[:30]
    report = {
        "desktop": DESKTOP.name,
        "criteria": {
            "min_lines": MIN_LINES,
            "max_lines": MAX_LINES,
            "min_functions": MIN_FUNCS,
            "max_functions": MAX_FUNCS,
            "max_gap": MAX_GAP,
        },
        "top_level_function_count": len(records),
        "strict_safe_function_count": len(safe_records),
        "candidate_batch_count": len(unique),
        "ranked_batches": ranked,
        "safe_functions": safe_records,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "top_level_function_count": len(records),
        "strict_safe_function_count": len(safe_records),
        "candidate_batch_count": len(unique),
        "top_batches": [
            {
                "score": batch["score"],
                "total_lines": batch["total_lines"],
                "functions": [item["name"] for item in batch["functions"]],
            }
            for batch in ranked[:10]
        ],
    }, ensure_ascii=True))


if __name__ == "__main__":
    main()
