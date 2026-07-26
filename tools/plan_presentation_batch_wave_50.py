from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
OUT = ROOT / "artifacts" / "wave-50-presentation-batch-plan.json"

LINE_START = 26000
MIN_HELPERS = 2
MAX_HELPERS = 10
MIN_LINES = 150
MAX_LINES = 500
MAX_GAP = 100

NAME_DENY = (
    "payment", "balance", "principal", "interest", "renew", "offset",
    "advance", "auto_close", "daily_close", "close_day", "due_rule",
    "route_notice", "report", "pdf", "backup", "restore", "migrat",
    "password", "login", "account", "role", "permission", "auth",
    "import", "export", "save", "write", "delete", "archive",
    "postgres", "_pg_", "fetch", "query", "transaction",
)

SOURCE_DENY = (
    "connect_db(", "self.db", ".execute(", ".executemany(", ".commit(",
    ".rollback(", "run_write(", "open(", "json.load", "json.dump",
    "_write_json_atomic", "write_text(", "write_bytes(", ".unlink(",
    "os.makedirs", "os.remove", "os.rename", "os.replace", "shutil.",
    "pathlib.", "root.after(", ".after(", "threading.", "subprocess.",
    "filedialog.", "INSERT INTO", "UPDATE ", "DELETE FROM ",
    "CREATE TABLE", "ALTER TABLE", "DROP TABLE", "SELECT ",
    "total_to_pay", "interest_amount", "remaining_balance", "principal",
    "payment", "renewal", "7x7", "adv", "pass ",
)

CALL_DENY_PREFIXES = (
    "os.", "json.", "shutil.", "pathlib.", "subprocess.", "threading.",
    "root.after", "self.db", "connect_db", "run_write", "open",
)

UI_MARKERS = (
    "tk.", "ttk.", "messagebox.", "simpledialog.", "toplevel",
    "frame", "button", "label", "tree", "style", "palette", "theme",
    "build", "dialog", "tab", "sidebar", "header", "chart", "card",
    "details", "selection", "refresh_", "configure",
)


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def norm_hash(source: str) -> str:
    normalized = "\n".join(line.rstrip() for line in source.strip().splitlines())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def top_level_functions(tree: ast.Module) -> list[ast.FunctionDef]:
    return [node for node in tree.body if isinstance(node, ast.FunctionDef)]


def is_ui_candidate(name: str, source: str, calls: list[str]) -> tuple[bool, list[str]]:
    lower_name = name.lower()
    lower_source = source.lower()
    reasons: list[str] = []

    for token in NAME_DENY:
        if token.lower() in lower_name:
            reasons.append(f"name:{token}")

    for token in SOURCE_DENY:
        if token.lower() in lower_source:
            reasons.append(f"source:{token}")

    for call in calls:
        low = call.lower()
        if any(low == prefix.lower() or low.startswith(prefix.lower()) for prefix in CALL_DENY_PREFIXES):
            reasons.append(f"call:{call}")

    has_ui_marker = any(marker.lower() in lower_name or marker.lower() in lower_source for marker in UI_MARKERS)
    if not has_ui_marker:
        reasons.append("no-ui-marker")

    # Presentation wrappers may call existing core actions, but should not define
    # calculations, persistence, scheduling, or permission decisions themselves.
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.With, ast.AsyncWith, ast.Import, ast.ImportFrom)):
            reasons.append(type(node).__name__)
        if isinstance(node, ast.Raise):
            reasons.append("raise")

    return not reasons, sorted(set(reasons))


def main() -> None:
    text = DESKTOP.read_text(encoding="utf-8")
    tree = ast.parse(text)
    records = []

    for node in top_level_functions(tree):
        if node.lineno < LINE_START:
            continue
        source = ast.get_source_segment(text, node) or ""
        calls = sorted({
            dotted(call.func)
            for call in ast.walk(node)
            if isinstance(call, ast.Call) and dotted(call.func)
        })
        safe, rejected_by = is_ui_candidate(node.name, source, calls)
        records.append({
            "name": node.name,
            "lineno": node.lineno,
            "end_lineno": node.end_lineno,
            "lines": (node.end_lineno or node.lineno) - node.lineno + 1,
            "signature": ast.unparse(node.args),
            "sha256": norm_hash(source),
            "calls": calls,
            "safe": safe,
            "rejected_by": rejected_by,
        })

    records.sort(key=lambda item: int(item["lineno"]))
    safe_records = [item for item in records if item["safe"]]

    blocks: list[list[dict[str, object]]] = []
    current: list[dict[str, object]] = []
    for item in safe_records:
        if current:
            gap = int(item["lineno"]) - int(current[-1]["end_lineno"] or current[-1]["lineno"])
            if gap > MAX_GAP:
                blocks.append(current)
                current = []
        current.append(item)
    if current:
        blocks.append(current)

    groups = []
    for block in blocks:
        for start in range(len(block)):
            for size in range(MIN_HELPERS, MAX_HELPERS + 1):
                window = block[start:start + size]
                if len(window) != size:
                    continue
                total = sum(int(item["lines"]) for item in window)
                if not (MIN_LINES <= total <= MAX_LINES):
                    continue
                groups.append({
                    "start_line": window[0]["lineno"],
                    "end_line": window[-1]["end_lineno"],
                    "helper_count": size,
                    "total_lines": total,
                    "score": total + size * 30,
                    "helpers": window,
                })

    groups.sort(
        key=lambda item: (int(item["score"]), int(item["total_lines"]), int(item["helper_count"])),
        reverse=True,
    )

    report = {
        "desktop": DESKTOP.name,
        "scanned": len(records),
        "safe": len(safe_records),
        "rejected": len(records) - len(safe_records),
        "group_count": len(groups),
        "top_groups": groups[:40],
        "safe_functions": safe_records,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({
        "scanned": len(records),
        "safe": len(safe_records),
        "rejected": len(records) - len(safe_records),
        "group_count": len(groups),
        "top": groups[0] if groups else None,
    }))


if __name__ == "__main__":
    main()
