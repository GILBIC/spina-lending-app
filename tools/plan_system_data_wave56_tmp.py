from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
OUT = ROOT / "artifacts" / "wave-56-system-data-candidate.json"
TARGET_CLASS = "App"
TARGET_METHOD = "_build_system_data_tab"


def dotted(node: ast.AST) -> str:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def main() -> None:
    text = APP.read_text(encoding="utf-8-sig")
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text, filename=str(APP))
    target: ast.FunctionDef | ast.AsyncFunctionDef | None = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == TARGET_CLASS:
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == TARGET_METHOD:
                    target = child
                    break
    if target is None or target.end_lineno is None:
        raise SystemExit(f"Missing {TARGET_CLASS}.{TARGET_METHOD}")

    source = "".join(lines[target.lineno - 1 : target.end_lineno])
    calls = sorted({dotted(n.func) for n in ast.walk(target) if isinstance(n, ast.Call) and dotted(n.func)})
    names = sorted({n.id for n in ast.walk(target) if isinstance(n, ast.Name)})
    lowered = "\n".join(calls + names).lower()
    protected_markers = [
        marker
        for marker in (
            ".execute", ".executemany", ".commit", ".rollback",
            "insert", "update_transaction", "delete_transaction",
            "set_transaction", "add_transaction", "close_day", "reopen_day",
            "backup", "restore", "password", "pg_dump", "filesystem",
        )
        if marker in lowered
    ]
    signature = ast.unparse(target.args)
    report = {
        "target": f"{TARGET_CLASS}.{TARGET_METHOD}",
        "start_line": target.lineno,
        "end_line": target.end_lineno,
        "lines": target.end_lineno - target.lineno + 1,
        "sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "signature": signature,
        "calls": calls,
        "protected_markers": protected_markers,
        "classification": "ui_only_candidate" if not protected_markers else "manual_review",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
