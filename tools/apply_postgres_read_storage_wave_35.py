from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
ARTIFACTS = ROOT / "artifacts"

ALREADY_EXTRACTED = {
    "_spina_pg_sha256",
    "_spina_pg_guess_file_type",
    "_spina_pg_guess_report_date",
    "_spina_pg_guess_collector",
    "_spina_pg_normalize_value",
    "_spina_pg_replace_qmarks",
    "_spina_pg_escape_literal_percents",
}
EXACT_SAFE = {
    "_spina_pg_storage_enabled",
    "_spina_pg_app_dir",
    "_spina_pg_relpath",
    "_spina_pg_json_table_for_path",
    "_spina_pg_read_json",
}
READ_NAME_PARTS = (
    "read", "load", "fetch", "find", "lookup", "list", "get", "exists",
    "enabled", "relpath", "app_dir", "json_table",
)
EXCLUDED_NAME_PARTS = (
    "write", "store", "save", "ensure", "sync", "import", "backup", "restore",
    "delete", "remove", "update", "insert", "upsert", "migrate", "schema",
    "commit", "rollback", "connect", "_conn", "_log",
)
SQL_WRITE_MARKERS = (
    "INSERT INTO", "UPDATE ", "DELETE FROM", "CREATE TABLE", "ALTER TABLE",
    "DROP TABLE", "TRUNCATE ", "REPLACE INTO", "ON CONFLICT",
)
MUTATING_ATTRS = {
    "commit", "rollback", "write", "write_text", "write_bytes", "unlink",
    "remove", "rename", "mkdir", "makedirs", "rmdir", "touch", "copy", "copy2", "move",
}


def inspect_helper(node: ast.AST, source: str) -> tuple[bool, list[str]]:
    name = node.name
    reasons: list[str] = []
    low = name.lower()
    if name in ALREADY_EXTRACTED:
        reasons.append("already extracted")
    if name not in EXACT_SAFE:
        if not any(part in low for part in READ_NAME_PARTS):
            reasons.append("name is not read/path/lookup oriented")
        if any(part in low for part in EXCLUDED_NAME_PARTS):
            reasons.append("name indicates mutation/connection/schema behavior")
    if any(marker in source.upper() for marker in SQL_WRITE_MARKERS):
        reasons.append("contains SQL write/schema marker")
    for item in ast.walk(node):
        if not isinstance(item, ast.Call):
            continue
        fn = item.func
        call_name = fn.attr if isinstance(fn, ast.Attribute) else fn.id if isinstance(fn, ast.Name) else ""
        if call_name.lower() in MUTATING_ATTRS:
            reasons.append(f"calls mutating helper {call_name}")
        if call_name == "open":
            mode = None
            if len(item.args) >= 2 and isinstance(item.args[1], ast.Constant):
                mode = item.args[1].value
            for kw in item.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                    mode = kw.value.value
            if isinstance(mode, str) and any(ch in mode for ch in "wax+"):
                reasons.append(f"opens file in mutating mode {mode}")
    return not reasons, sorted(set(reasons))


def main() -> None:
    text = DESKTOP.read_text(encoding="utf-8-sig")
    tree = ast.parse(text, filename=str(DESKTOP))
    rows = []
    accepted_lines = 0
    all_lines = 0
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("_spina_pg_"):
            continue
        source = ast.get_source_segment(text, node) or ""
        line_count = (node.end_lineno or node.lineno) - node.lineno + 1
        accepted, reasons = inspect_helper(node, source)
        all_lines += line_count
        if accepted:
            accepted_lines += line_count
        rows.append({
            "name": node.name,
            "line": node.lineno,
            "lines": line_count,
            "accepted": accepted,
            "reasons": reasons,
        })

    ARTIFACTS.mkdir(exist_ok=True)
    payload = {
        "accepted_lines": accepted_lines,
        "all_postgres_helper_lines": all_lines,
        "functions": rows,
    }
    (ARTIFACTS / "wave35-inventory.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    markdown = [
        "# Wave 35 PostgreSQL helper inventory",
        "",
        f"First guard accepted **{accepted_lines} lines** from **{all_lines} total PostgreSQL helper lines**.",
        "",
    ]
    for row in rows:
        status = "accepted" if row["accepted"] else "excluded: " + "; ".join(row["reasons"])
        markdown.append(f"- `{row['name']}` — {row['lines']} lines — {status}")
    (ARTIFACTS / "wave35-inventory.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    print(f"Wave 35 inventory complete: {accepted_lines} accepted lines across {len(rows)} PostgreSQL helpers.")


if __name__ == "__main__":
    main()
