from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
OUT = ROOT / "artifacts" / "wave-50-high-volume-presentation-plan.json"

LINE_START = 25000
MIN_HELPERS = 3
MAX_HELPERS = 12
MIN_LINES = 100
MAX_LINES = 450
MAX_GAP = 220

PROTECTED_FRAGMENTS = (
    "password", "verify_login", "hash_password", "force_change_password",
    "must_change_password", "save_users", "account_migration", "role_access",
    "permission", "psycopg", "sqlite3", "connect_db", "run_write",
    ".execute(", ".executemany(", ".commit(", ".rollback(",
    "insert into", "update ", "delete from", "alter table", "create table",
    "drop table", "payment", "balance", "principal", "interest", "renew",
    "offset", "advance", "adv_", "pass_", "7x7", "day_close", "close_day",
    "import", "export", "report", "pdf", "backup", "restore", "migration",
    "open(", "write_text", "write_bytes", "unlink", "mkdir", "rmdir",
    "copy", "move", "rename", "replace(", "remove(", "delete_",
)

PROTECTED_NAME_PARTS = (
    "payment", "balance", "principal", "interest", "renew", "offset",
    "advance", "pass", "7x7", "report", "pdf", "backup", "restore",
    "migrat", "password", "login", "auth", "permission", "role_access",
    "save", "write", "delete", "insert", "commit", "rollback", "close_day",
    "day_close", "import", "export",
)

PRESENTATION_PARTS = (
    "build", "theme", "style", "layout", "dialog", "tab", "tree", "card",
    "header", "palette", "editor", "button", "label", "search", "navigation",
    "filter", "resize", "configure", "display", "select", "toggle", "frame",
    "window", "panel", "status", "summary", "refresh", "toolbar", "grid",
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


def top_level_functions(tree: ast.Module) -> list[ast.FunctionDef]:
    return [node for node in tree.body if isinstance(node, ast.FunctionDef)]


def family_for(name: str) -> str:
    version = re.match(r"(_spina_v\d+)_", name)
    if version:
        return version.group(1)
    pieces = [part for part in name.split("_") if part]
    return "_".join(pieces[:3])


def active_bindings(tree: ast.Module) -> dict[str, list[str]]:
    bindings: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        value_names = {
            part.id for part in ast.walk(node.value)
            if isinstance(part, ast.Name)
        }
        for target in node.targets:
            target_name = dotted(target)
            if not target_name.startswith("App."):
                continue
            for value_name in value_names:
                bindings.setdefault(value_name, []).append(target_name)
    return bindings


def record(text: str, node: ast.FunctionDef, bindings: dict[str, list[str]]) -> dict[str, object]:
    source = ast.get_source_segment(text, node) or ""
    lower = source.lower()
    calls = sorted({
        dotted(call.func)
        for call in ast.walk(node)
        if isinstance(call, ast.Call) and dotted(call.func)
    })
    protected_hits = sorted({
        fragment for fragment in PROTECTED_FRAGMENTS if fragment in lower
    })
    lower_name = node.name.lower()
    protected_name_hits = sorted({
        part for part in PROTECTED_NAME_PARTS if part in lower_name
    })
    presentation_hits = sorted({
        part for part in PRESENTATION_PARTS if part in lower_name
    })
    lines = (node.end_lineno or node.lineno) - node.lineno + 1
    return {
        "name": node.name,
        "family": family_for(node.name),
        "lineno": node.lineno,
        "end_lineno": node.end_lineno,
        "lines": lines,
        "signature": ast.unparse(node.args),
        "sha256": normalized_hash(source),
        "calls": calls,
        "protected_hits": protected_hits,
        "protected_name_hits": protected_name_hits,
        "presentation_hits": presentation_hits,
        "active_bindings": sorted(set(bindings.get(node.name, []))),
        "source": source,
    }


def main() -> None:
    text = DESKTOP.read_text(encoding="utf-8")
    tree = ast.parse(text)
    bindings = active_bindings(tree)
    records = [
        record(text, node, bindings)
        for node in top_level_functions(tree)
        if node.lineno >= LINE_START
    ]
    records.sort(key=lambda item: int(item["lineno"]))

    safe = [
        item for item in records
        if not item["protected_hits"] and not item["protected_name_hits"]
    ]

    blocks: list[list[dict[str, object]]] = []
    current: list[dict[str, object]] = []
    for item in safe:
        if not current:
            current = [item]
            continue
        previous = current[-1]
        gap = int(item["lineno"]) - int(previous["end_lineno"] or previous["lineno"])
        same_family = item["family"] == previous["family"]
        both_bound = bool(item["active_bindings"]) and bool(previous["active_bindings"])
        if gap <= MAX_GAP and (same_family or both_bound):
            current.append(item)
        else:
            blocks.append(current)
            current = [item]
    if current:
        blocks.append(current)

    groups: list[dict[str, object]] = []
    for block in blocks:
        for start in range(len(block)):
            for size in range(MIN_HELPERS, MAX_HELPERS + 1):
                window = block[start : start + size]
                if len(window) != size:
                    continue
                total_lines = sum(int(item["lines"]) for item in window)
                if not MIN_LINES <= total_lines <= MAX_LINES:
                    continue
                active_count = sum(bool(item["active_bindings"]) for item in window)
                presentation_count = sum(len(item["presentation_hits"]) for item in window)
                wrapper_count = sum(
                    1 for item in window
                    if any("orig" in call or "prev" in call for call in item["calls"])
                )
                distinct_families = len({str(item["family"]) for item in window})
                score = (
                    active_count * 10000
                    + presentation_count * 1000
                    + wrapper_count * 250
                    + total_lines
                    - max(0, distinct_families - 1) * 500
                )
                groups.append({
                    "start_line": window[0]["lineno"],
                    "end_line": window[-1]["end_lineno"],
                    "helper_count": size,
                    "total_lines": total_lines,
                    "active_binding_count": active_count,
                    "presentation_hit_count": presentation_count,
                    "wrapper_count": wrapper_count,
                    "families": sorted({str(item["family"]) for item in window}),
                    "score": score,
                    "helpers": window,
                })

    groups.sort(key=lambda item: int(item["score"]), reverse=True)
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
        "safe_functions": safe,
        "candidate_group_count": len(groups),
        "top_groups": groups[:40],
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
