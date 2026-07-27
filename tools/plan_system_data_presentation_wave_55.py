from __future__ import annotations

# Wave 55 candidate inspection runs only on the feature branch.
import ast
import hashlib
from pathlib import Path

SOURCE = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
TARGETS = (
    "_show_system_data_tab",
    "_hide_system_data_tab",
    "_system_data_get_date",
    "_system_data_use_focus_date",
    "_system_data_refresh_summary",
    "_system_data_open_close",
    "_system_data_open_history",
    "_system_data_open_records",
    "_system_data_print_report",
    "_build_system_data_tab",
)
WRITE_MARKERS = {
    "add_client", "update_client", "renew_client", "delete_client", "archive_client",
    "set_transaction", "save_transaction", "close_day", "reopen_day", "run_write",
    "execute", "executemany", "commit", "rollback", "save_settings", "write_text",
    "write_bytes", "unlink", "remove", "replace", "rename", "mkdir",
}


def dotted(node: ast.AST) -> str:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def main() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text)
    app = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "App")
    methods = {n.name: n for n in app.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}

    missing = [name for name in TARGETS if name not in methods]
    if missing:
        raise SystemExit(f"Missing App methods: {missing}")

    total = 0
    pieces: list[str] = []
    for name in TARGETS:
        node = methods[name]
        start = node.lineno
        end = node.end_lineno or node.lineno
        source = "".join(lines[start - 1:end])
        calls = sorted({dotted(n.func) for n in ast.walk(node) if isinstance(n, ast.Call) and dotted(n.func)})
        write_like = sorted({call for call in calls if call.rsplit(".", 1)[-1].lower() in WRITE_MARKERS})
        line_count = end - start + 1
        total += line_count
        pieces.append(
            f"{name}:start={start},end={end},lines={line_count},"
            f"sha={hashlib.sha256(source.encode('utf-8')).hexdigest()},"
            f"write_like={','.join(write_like) or '-'}"
        )

    print(f"WAVE55_PLAN|methods={len(TARGETS)}|total_lines={total}|" + ";".join(pieces))


if __name__ == "__main__":
    main()
