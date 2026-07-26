from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
OUT = ROOT / "artifacts" / "wave-48-high-volume-batch-plan.json"

LINE_START = 26000
MIN_HELPERS = 5
MAX_HELPERS = 12
MIN_LINES = 150
MAX_LINES = 400
MAX_GAP = 40

PROTECTED_TOKENS = {
    "payment", "payments", "balance", "balances", "principal", "interest",
    "renew", "renewal", "renewals", "offset", "advance", "adv", "pass",
    "7x7", "report", "reports", "pdf", "backup", "restore", "migration",
    "migrate", "password", "verify_login", "hash_password",
    "force_change_password", "must_change_password", "save_users_db",
    "write_users", "execute", "executemany", "commit", "rollback",
    "insert", "update", "delete", "open", "write_text", "write_bytes",
    "unlink", "mkdir", "rmdir", "replace", "rename", "copy", "move",
}

EXCLUDED_NAME_PARTS = (
    "payment", "balance", "principal", "interest", "renew", "offset",
    "advance", "7x7", "report", "pdf", "backup", "restore", "migrat",
    "password", "verify_login", "auth", "write", "save", "delete",
    "insert", "update_db", "commit", "rollback",
)


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def normalized_hash(source: str) -> str:
    normalized = "\n".join(line.rstrip() for line in source.strip().splitlines())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def token_parts(value: str) -> set[str]:
    cleaned = value.lower().replace("-", "_").replace(".", "_")
    return {part for part in cleaned.split("_") if part}


def top_level_functions(tree: ast.Module) -> list[ast.FunctionDef]:
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent

    result: list[ast.FunctionDef] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        ancestor = parents.get(node)
        nested = False
        while ancestor is not None:
            if isinstance(ancestor, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
                nested = True
                break
            ancestor = parents.get(ancestor)
        if not nested:
            result.append(node)
    return result


def active_bindings(tree: ast.Module) -> dict[str, list[str]]:
    bindings: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Name):
            continue
        value_name = node.value.id
        for target in node.targets:
            target_name = dotted(target)
            if target_name.startswith("App.") or target_name.startswith("globals."):
                bindings.setdefault(value_name, []).append(target_name)
    return bindings


def function_record(text: str, node: ast.FunctionDef, bindings: dict[str, list[str]]) -> dict[str, object]:
    source = ast.get_source_segment(text, node) or ""
    calls = sorted({
        dotted(call.func)
        for call in ast.walk(node)
        if isinstance(call, ast.Call) and dotted(call.func)
    })
    identifiers = {part.id.lower() for part in ast.walk(node) if isinstance(part, ast.Name)}
    attrs = {part.attr.lower() for part in ast.walk(node) if isinstance(part, ast.Attribute)}
    call_parts: set[str] = set()
    for call in calls:
        call_parts.update(token_parts(call))
    name_parts = token_parts(node.name)
    protected_hits = sorted(
        (identifiers | attrs | call_parts | name_parts) & PROTECTED_TOKENS
    )
    lower_name = node.name.lower()
    excluded_name_hits = sorted(part for part in EXCLUDED_NAME_PARTS if part in lower_name)
    return {
        "name": node.name,
        "lineno": node.lineno,
        "end_lineno": node.end_lineno,
        "lines": (node.end_lineno or node.lineno) - node.lineno + 1,
        "signature": ast.unparse(node.args),
        "sha256": normalized_hash(source),
        "calls": calls,
        "protected_hits": protected_hits,
        "excluded_name_hits": excluded_name_hits,
        "active_bindings": sorted(bindings.get(node.name, [])),
    }


def main() -> None:
    text = DESKTOP.read_text(encoding="utf-8")
    tree = ast.parse(text)
    bindings = active_bindings(tree)
    records = [
        function_record(text, node, bindings)
        for node in top_level_functions(tree)
        if node.lineno >= LINE_START
    ]
    records.sort(key=lambda item: int(item["lineno"]))

    safe = [
        item for item in records
        if not item["protected_hits"] and not item["excluded_name_hits"]
    ]

    contiguous_blocks: list[list[dict[str, object]]] = []
    current: list[dict[str, object]] = []
    for item in safe:
        if not current:
            current = [item]
            continue
        previous = current[-1]
        gap = int(item["lineno"]) - int(previous["end_lineno"] or previous["lineno"])
        if gap <= MAX_GAP:
            current.append(item)
        else:
            if current:
                contiguous_blocks.append(current)
            current = [item]
    if current:
        contiguous_blocks.append(current)

    groups: list[dict[str, object]] = []
    for block in contiguous_blocks:
        for start in range(len(block)):
            for size in range(MIN_HELPERS, MAX_HELPERS + 1):
                window = block[start : start + size]
                if len(window) != size:
                    continue
                total_lines = sum(int(item["lines"]) for item in window)
                if not (MIN_LINES <= total_lines <= MAX_LINES):
                    continue
                bound_count = sum(1 for item in window if item["active_bindings"])
                groups.append({
                    "start_line": window[0]["lineno"],
                    "end_line": window[-1]["end_lineno"],
                    "helper_count": size,
                    "total_lines": total_lines,
                    "active_binding_count": bound_count,
                    "score": bound_count * 1000 + total_lines,
                    "helpers": window,
                })

    groups.sort(
        key=lambda item: (
            int(item["active_binding_count"]),
            int(item["total_lines"]),
            int(item["helper_count"]),
        ),
        reverse=True,
    )

    report = {
        "desktop": DESKTOP.name,
        "constraints": {
            "line_start": LINE_START,
            "helper_range": [MIN_HELPERS, MAX_HELPERS],
            "line_range": [MIN_LINES, MAX_LINES],
            "max_gap": MAX_GAP,
        },
        "scanned_function_count": len(records),
        "safe_function_count": len(safe),
        "candidate_group_count": len(groups),
        "top_groups": groups[:30],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "scanned_function_count": len(records),
        "safe_function_count": len(safe),
        "candidate_group_count": len(groups),
        "top_group": groups[0] if groups else None,
    }, ensure_ascii=True))


if __name__ == "__main__":
    main()
