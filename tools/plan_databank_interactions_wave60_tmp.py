from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
OUT = ROOT / "artifacts" / "wave-60-databank-interactions.json"
TARGET_CLASS = "App"
NAME_HINTS = (
    "cell", "databank", "missed", "mousewheel", "resize_databank", "data_toolbar",
)
PROTECTED = (
    ".execute", ".executemany", ".commit", ".rollback",
    "add_or_update_transaction", "delete_transaction", "delete_transactions_for_day",
    "set_databank_day_close", "close_day", "reopen_day", "import", "backup", "restore",
    "write_text", "write_bytes", "unlink", "remove(", "print", "pdf",
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
    app = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == TARGET_CLASS)
    reports = []
    for node in app.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        low_name = node.name.lower()
        if not any(h in low_name for h in NAME_HINTS):
            continue
        if node.end_lineno is None:
            continue
        source = "".join(lines[node.lineno - 1:node.end_lineno])
        calls = sorted({dotted(c.func) for c in ast.walk(node) if isinstance(c, ast.Call) and dotted(c.func)})
        joined = "\n".join(calls).lower()
        hits = [p for p in PROTECTED if p.lower() in joined or p.lower() in source.lower()]
        reports.append({
            "name": node.name,
            "start": node.lineno,
            "end": node.end_lineno,
            "lines": node.end_lineno - node.lineno + 1,
            "signature": ast.unparse(node.args),
            "sha256": hashlib.sha256(source.encode()).hexdigest(),
            "calls": calls,
            "db_calls": [c for c in calls if c.startswith("self.db.")],
            "protected": hits,
            "classification": "write_or_protected" if hits else "presentation_or_support",
        })
    reports.sort(key=lambda r: r["start"])
    summary = {
        "base_commit": "a4c6fbaefc5c366270261b887e67a7fca819ccdd",
        "candidate_count": len(reports),
        "total_lines": sum(r["lines"] for r in reports),
        "clean_lines": sum(r["lines"] for r in reports if r["classification"] == "presentation_or_support"),
        "protected_lines": sum(r["lines"] for r in reports if r["classification"] == "write_or_protected"),
        "candidates": reports,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
