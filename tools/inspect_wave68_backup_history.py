from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
SOURCE_OUT = ROOT / "docs" / "wave68-backup-history-source.txt"
META_OUT = ROOT / "docs" / "wave68-backup-history-meta.json"
TARGET = "open_backup_history_window"
EXPECTED_LINES = 182
EXPECTED_SHA256 = "c05501298b2aa308c66f0f668bb482a96de8dc221b098f88705fa6d452c6d59f"


def dotted(node: ast.AST | None) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return dotted(node.func)
    if isinstance(node, ast.Subscript):
        return dotted(node.value)
    return ""


def main() -> None:
    text = APP.read_text(encoding="utf-8")
    tree = ast.parse(text)
    app = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "App")
    node = next(n for n in app.body if isinstance(n, ast.FunctionDef) and n.name == TARGET)
    lines = text.splitlines(keepends=True)
    source = "".join(lines[node.lineno - 1:node.end_lineno]).replace("\r\n", "\n")
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    assert node.end_lineno - node.lineno + 1 == EXPECTED_LINES
    assert digest == EXPECTED_SHA256

    calls = sorted({
        dotted(item.func)
        for item in ast.walk(node)
        if isinstance(item, ast.Call) and dotted(item.func)
    })
    db_calls = sorted(c for c in calls if c.startswith("self.db") or ".db." in c)
    nested = [
        item.name for item in node.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    attributes = sorted({
        dotted(item) for item in ast.walk(node)
        if isinstance(item, ast.Attribute) and dotted(item).startswith("self.")
    })

    SOURCE_OUT.write_text(source, encoding="utf-8")
    META_OUT.write_text(json.dumps({
        "target": TARGET,
        "lines": EXPECTED_LINES,
        "source_sha256": digest,
        "signature": ast.unparse(node.args),
        "nested_callbacks": nested,
        "calls": calls,
        "db_calls": db_calls,
        "self_attributes": attributes,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Exported {TARGET}: {EXPECTED_LINES} lines, {digest}")


if __name__ == "__main__":
    main()
