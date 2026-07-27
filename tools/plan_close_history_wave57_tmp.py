from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
OUT = ROOT / "artifacts" / "wave-57-close-history-candidate.json"
TARGET_CLASS = "App"
TARGET_METHOD = "open_databank_close_history_dialog"

WRITE_MARKERS = (
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


def find_target(tree: ast.Module) -> ast.FunctionDef | ast.AsyncFunctionDef:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == TARGET_CLASS:
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == TARGET_METHOD:
                    return child
    raise SystemExit(f"Missing {TARGET_CLASS}.{TARGET_METHOD}")


def main() -> None:
    original_text = APP.read_text(encoding="utf-8-sig")
    text = original_text.replace("\r\n", "\n")
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text, filename=str(APP))
    target = find_target(tree)
    if target.end_lineno is None:
        raise SystemExit("Target end line missing")

    source = "".join(lines[target.lineno - 1 : target.end_lineno])
    calls = sorted(
        {
            dotted(node.func)
            for node in ast.walk(target)
            if isinstance(node, ast.Call) and dotted(node.func)
        }
    )
    names = sorted({node.id for node in ast.walk(target) if isinstance(node, ast.Name)})
    self_store_attrs = sorted(
        {
            node.attr
            for node in ast.walk(target)
            if isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
            and isinstance(node.ctx, ast.Store)
        }
    )
    nested_functions = sorted(
        node.name
        for node in ast.walk(target)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node is not target
    )
    literal_texts = sorted(
        {
            value.value
            for value in ast.walk(target)
            if isinstance(value, ast.Constant)
            and isinstance(value.value, str)
            and value.value.strip()
            and len(value.value) <= 120
        }
    )
    lowered = "\n".join(calls + names + literal_texts).lower()
    write_hits = [marker for marker in WRITE_MARKERS if marker.lower() in lowered]
    signature = ast.unparse(target.args)
    report = {
        "target": f"{TARGET_CLASS}.{TARGET_METHOD}",
        "start_line": target.lineno,
        "end_line": target.end_lineno,
        "lines": target.end_lineno - target.lineno + 1,
        "sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "signature": signature,
        "calls": calls,
        "names": names,
        "self_store_attributes": self_store_attrs,
        "nested_functions": nested_functions,
        "literal_texts": literal_texts,
        "write_markers": write_hits,
        "classification": "ui_read_candidate" if not write_hits else "manual_review",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
