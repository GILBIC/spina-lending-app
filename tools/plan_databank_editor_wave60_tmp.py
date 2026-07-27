from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
OUT = ROOT / "artifacts" / "wave-60-databank-editor-candidates.json"
SOURCE_DIR = ROOT / "artifacts" / "wave-60-databank-editor-sources"
TARGET_CLASS = "App"
TARGETS = (
    "_pick_missed_reason",
    "_walk_widgets",
    "_begin_cell_edit",
    "_remember_cell_click",
)

DIRECT_WRITE_MARKERS = (
    ".execute",
    ".executemany",
    ".commit",
    ".rollback",
    "add_or_update_transaction",
    "delete_transaction",
    "delete_transactions_for_day",
    "set_databank_day_close",
    "replace_databank_day_collectors",
    "close_day",
    "reopen_day",
    "write_text",
    "write_bytes",
    "unlink",
    "remove(",
)
DELEGATED_WRITE_CALLBACKS = (
    "self._save_cell_edit",
    "self.delete_selected_cell",
    "self._mark_missed_for_selected",
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
        raise SystemExit(f"Missing Wave 60 candidates: {missing}")

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
        direct_hits = [m for m in DIRECT_WRITE_MARKERS if m.lower() in lowered]
        delegated = [c for c in DELEGATED_WRITE_CALLBACKS if c in calls]
        db_calls = [call for call in calls if call.startswith("self.db.")]
        classification = "presentation_candidate"
        if direct_hits or db_calls:
            classification = "protected_or_side_effecting"
        elif delegated:
            classification = "presentation_with_delegated_write_callback"
        report = {
            "target": f"{TARGET_CLASS}.{name}",
            "start_line": node.lineno,
            "end_line": node.end_lineno,
            "lines": node.end_lineno - node.lineno + 1,
            "sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
            "signature": ast.unparse(node.args),
            "calls": calls,
            "db_calls": db_calls,
            "direct_write_markers": direct_hits,
            "delegated_write_callbacks": delegated,
            "classification": classification,
        }
        reports.append(report)
        (SOURCE_DIR / f"{name}.py").write_text(source, encoding="utf-8")

    summary = {
        "base_commit": "a4c6fbaefc5c366270261b887e67a7fca819ccdd",
        "targets": [report["target"] for report in reports],
        "total_lines": sum(int(report["lines"]) for report in reports),
        "all_without_direct_writes": all(
            not report["direct_write_markers"] and not report["db_calls"]
            for report in reports
        ),
        "candidates": reports,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
