from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
OUT = ROOT / "artifacts" / "wave-59-system-data-navigation-candidates.json"
SOURCE_DIR = ROOT / "artifacts" / "wave-59-system-data-navigation-sources"
TARGET_CLASS = "App"
TARGETS = (
    "_get_databank_focus_date",
    "_show_system_data_tab",
    "_hide_system_data_tab",
    "_system_data_open_close",
    "_system_data_open_history",
    "_system_data_open_records",
    "_system_data_print_report",
)
PREFERRED = {
    "_get_databank_focus_date",
    "_show_system_data_tab",
    "_hide_system_data_tab",
    "_system_data_open_history",
    "_system_data_open_records",
}
PROTECTED_MARKERS = (
    ".execute", ".executemany", ".commit", ".rollback",
    "set_databank_day_close", "replace_databank_day_collectors",
    "delete_transactions_for_day", "delete_transaction",
    "add_or_update_transaction", "close_day", "reopen_day",
    "backup", "restore", "password", "print_databank_close_report",
    "write_text", "write_bytes", "unlink", "remove(",
)


def dotted(node: ast.AST) -> str:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def main() -> None:
    text = APP.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text, filename=str(APP))
    app_class = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == TARGET_CLASS
    )
    methods = {
        node.name: node for node in app_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in TARGETS
    }
    missing = sorted(set(TARGETS) - set(methods))
    if missing:
        raise SystemExit(f"Missing Wave 59 candidates: {missing}")

    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    reports: list[dict[str, object]] = []
    for name in TARGETS:
        node = methods[name]
        if node.end_lineno is None:
            raise SystemExit(f"Missing end line for {name}")
        source = "".join(lines[node.lineno - 1:node.end_lineno])
        calls = sorted({
            dotted(call.func)
            for call in ast.walk(node)
            if isinstance(call, ast.Call) and dotted(call.func)
        })
        lowered = "\n".join(calls).lower()
        hits = [marker for marker in PROTECTED_MARKERS if marker.lower() in lowered]
        report = {
            "target": f"{TARGET_CLASS}.{name}",
            "start_line": node.lineno,
            "end_line": node.end_lineno,
            "lines": node.end_lineno - node.lineno + 1,
            "sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
            "signature": ast.unparse(node.args),
            "calls": calls,
            "db_calls": [call for call in calls if call.startswith("self.db.")],
            "protected_markers": hits,
            "preferred": name in PREFERRED,
            "classification": "presentation_candidate" if not hits else "protected_or_side_effecting",
        }
        reports.append(report)
        (SOURCE_DIR / f"{name}.py").write_text(source, encoding="utf-8")

    preferred = [report for report in reports if report["preferred"]]
    summary = {
        "base_commit": "3ecada5ab18eaa38f237160b6cc981e0ec3da8b1",
        "preferred_targets": [report["target"] for report in preferred],
        "preferred_total_lines": sum(int(report["lines"]) for report in preferred),
        "preferred_all_clean": all(report["classification"] == "presentation_candidate" for report in preferred),
        "candidates": reports,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
