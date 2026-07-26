from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
OUT = ROOT / "artifacts" / "wave-50-presentation-batch-plan.json"

LINE_START = 26000
MIN_HELPERS = 5
MAX_HELPERS = 12
MIN_LINES = 150
MAX_LINES = 450
MAX_GAP = 45

PROTECTED = {
    "payment", "balance", "principal", "interest", "renew", "renewal",
    "offset", "advance", "adv", "pass", "7x7", "report", "pdf", "backup",
    "restore", "migrate", "migration", "password", "auth", "permission",
    "role_access", "connect_db", "run_write", "execute", "executemany",
    "commit", "rollback", "insert", "delete", "update", "write_text",
    "write_bytes", "unlink", "mkdir", "rename", "replace", "copy", "move",
    "import", "export", "close_day", "day_close",
}


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def parts(value: str) -> set[str]:
    cleaned = value.lower().replace("-", "_").replace(".", "_")
    return {item for item in cleaned.split("_") if item}


def norm_hash(source: str) -> str:
    normalized = "\n".join(line.rstrip() for line in source.strip().splitlines())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def top_level_functions(tree: ast.Module) -> list[ast.FunctionDef]:
    return [node for node in tree.body if isinstance(node, ast.FunctionDef)]


def main() -> None:
    text = DESKTOP.read_text(encoding="utf-8")
    tree = ast.parse(text)
    records = []
    for node in top_level_functions(tree):
        if node.lineno < LINE_START:
            continue
        source = ast.get_source_segment(text, node) or ""
        calls = sorted({dotted(call.func) for call in ast.walk(node) if isinstance(call, ast.Call) and dotted(call.func)})
        tokens = parts(node.name)
        for call in calls:
            tokens.update(parts(call))
        hits = sorted(tokens & PROTECTED)
        records.append({
            "name": node.name,
            "lineno": node.lineno,
            "end_lineno": node.end_lineno,
            "lines": (node.end_lineno or node.lineno) - node.lineno + 1,
            "signature": ast.unparse(node.args),
            "sha256": norm_hash(source),
            "calls": calls,
            "protected_hits": hits,
        })
    records.sort(key=lambda item: int(item["lineno"]))
    safe = [item for item in records if not item["protected_hits"]]

    blocks = []
    current = []
    for item in safe:
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
                if MIN_LINES <= total <= MAX_LINES:
                    groups.append({
                        "start_line": window[0]["lineno"],
                        "end_line": window[-1]["end_lineno"],
                        "helper_count": size,
                        "total_lines": total,
                        "score": total + size * 25,
                        "helpers": window,
                    })
    groups.sort(key=lambda item: (int(item["score"]), int(item["total_lines"])), reverse=True)
    report = {
        "desktop": DESKTOP.name,
        "scanned": len(records),
        "safe": len(safe),
        "group_count": len(groups),
        "top_groups": groups[:40],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"scanned": len(records), "safe": len(safe), "group_count": len(groups), "top": groups[0] if groups else None}))


if __name__ == "__main__":
    main()
