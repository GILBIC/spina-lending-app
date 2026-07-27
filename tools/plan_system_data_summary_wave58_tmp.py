from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
OUT = ROOT / "artifacts" / "wave-58-system-data-helper-candidates.json"
SOURCE_DIR = ROOT / "artifacts" / "wave-58-system-data-sources"
TARGET_CLASS = "App"
PREFERRED_NAMES = {
    "_system_data_use_focus_date",
    "_system_data_refresh_summary",
}

PROTECTED_MARKERS = (
    ".execute",
    ".executemany",
    ".commit",
    ".rollback",
    "set_databank_day_close",
    "replace_databank_day_collectors",
    "delete_transactions_for_day",
    "delete_transaction",
    "add_or_update_transaction",
    "close_day",
    "reopen_day",
    "backup",
    "restore",
    "password",
    "print_databank_close_report",
    "write_text",
    "write_bytes",
    "unlink",
    "remove(",
)


def dotted(node: ast.AST) -> str:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def find_methods(tree: ast.Module) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == TARGET_CLASS:
            return {
                child.name: child
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                and child.name.startswith("_system_data_")
            }
    raise SystemExit(f"Missing class {TARGET_CLASS}")


def main() -> None:
    original = APP.read_text(encoding="utf-8-sig")
    text = original.replace("\r\n", "\n")
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text, filename=str(APP))
    methods = find_methods(tree)
    if not methods:
        raise SystemExit("No current App._system_data_* helpers found")

    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    reports: list[dict[str, object]] = []
    for name, node in sorted(methods.items(), key=lambda pair: pair[1].lineno):
        if node.end_lineno is None:
            raise SystemExit(f"Missing end line for {name}")
        source = "".join(lines[node.lineno - 1 : node.end_lineno])
        calls = sorted({
            dotted(call.func)
            for call in ast.walk(node)
            if isinstance(call, ast.Call) and dotted(call.func)
        })
        db_calls = [call for call in calls if call.startswith("self.db.")]
        literal_texts = sorted({
            item.value
            for item in ast.walk(node)
            if isinstance(item, ast.Constant)
            and isinstance(item.value, str)
            and item.value.strip()
            and len(item.value) <= 160
        })
        lowered = "\n".join(calls + literal_texts).lower()
        hits = [marker for marker in PROTECTED_MARKERS if marker.lower() in lowered]
        report = {
            "target": f"{TARGET_CLASS}.{name}",
            "start_line": node.lineno,
            "end_line": node.end_lineno,
            "lines": node.end_lineno - node.lineno + 1,
            "sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
            "signature": ast.unparse(node.args),
            "calls": calls,
            "db_calls": db_calls,
            "protected_markers": hits,
            "classification": "ui_read_candidate" if not hits else "protected_or_side_effecting",
        }
        reports.append(report)
        (SOURCE_DIR / f"{name}.py").write_text(source, encoding="utf-8")

    preferred = [
        report for report in reports
        if report["target"].split(".")[-1] in PREFERRED_NAMES
    ]
    summary = {
        "base_commit": "883907675bc64ede2916e7fe4ab167799f559ebf",
        "discovered_names": [report["target"].split(".")[-1] for report in reports],
        "preferred_targets": [report["target"] for report in preferred],
        "preferred_total_lines": sum(int(report["lines"]) for report in preferred),
        "preferred_all_present": PREFERRED_NAMES.issubset(methods),
        "preferred_all_clean": bool(preferred) and all(
            report["classification"] == "ui_read_candidate" for report in preferred
        ),
        "candidates": reports,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
