from __future__ import annotations

import ast
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
OUT = ROOT / "artifacts" / "wave-50-remaining-presentation-families.json"
LINE_START = 25000

PRESENTATION_PARTS = (
    "build", "theme", "style", "layout", "dialog", "tab", "tree", "card",
    "header", "palette", "editor", "button", "label", "search", "navigation",
    "filter", "resize", "configure", "display", "select", "toggle", "frame",
    "window", "panel", "status", "summary", "refresh", "toolbar", "grid",
    "colors", "font", "notice", "route", "collector", "account",
)

HIGH_RISK_CALL_PARTS = (
    "execute", "executemany", "commit", "rollback", "connect_db", "run_write",
    "save", "delete", "insert", "update", "write", "unlink", "mkdir", "rmdir",
    "copy", "move", "rename", "replace", "open", "export", "import",
)

BUSINESS_NAME_PARTS = (
    "payment", "balance", "principal", "interest", "renew", "offset", "advance",
    "pass", "7x7", "day_close", "close_day", "report", "pdf", "backup",
    "restore", "password", "login", "auth", "permission", "role_access",
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


def family_for(name: str) -> str:
    version = re.match(r"(_spina_v\d+)_", name)
    if version:
        return version.group(1)
    pieces = [part for part in name.split("_") if part]
    return "_".join(pieces[:3])


def active_bindings(tree: ast.Module) -> dict[str, list[str]]:
    result: dict[str, list[str]] = defaultdict(list)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        values = {part.id for part in ast.walk(node.value) if isinstance(part, ast.Name)}
        for target in node.targets:
            target_name = dotted(target)
            if not target_name.startswith("App."):
                continue
            for value in values:
                result[value].append(target_name)
    return result


def main() -> None:
    text = DESKTOP.read_text(encoding="utf-8")
    tree = ast.parse(text)
    bindings = active_bindings(tree)
    families: dict[str, list[dict[str, object]]] = defaultdict(list)

    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.lineno < LINE_START:
            continue
        source = ast.get_source_segment(text, node) or ""
        lower_name = node.name.lower()
        calls = sorted({
            dotted(call.func)
            for call in ast.walk(node)
            if isinstance(call, ast.Call) and dotted(call.func)
        })
        presentation_hits = sorted({part for part in PRESENTATION_PARTS if part in lower_name})
        business_name_hits = sorted({part for part in BUSINESS_NAME_PARTS if part in lower_name})
        risky_calls = sorted({
            call for call in calls
            if any(part in call.lower() for part in HIGH_RISK_CALL_PARTS)
        })
        families[family_for(node.name)].append({
            "name": node.name,
            "lineno": node.lineno,
            "end_lineno": node.end_lineno,
            "lines": (node.end_lineno or node.lineno) - node.lineno + 1,
            "signature": ast.unparse(node.args),
            "sha256": normalized_hash(source),
            "calls": calls,
            "risky_calls": risky_calls,
            "presentation_hits": presentation_hits,
            "business_name_hits": business_name_hits,
            "active_bindings": sorted(set(bindings.get(node.name, []))),
            "source": source,
        })

    family_rows = []
    for family, helpers in families.items():
        helpers.sort(key=lambda item: int(item["lineno"]))
        total_lines = sum(int(item["lines"]) for item in helpers)
        presentation_count = sum(len(item["presentation_hits"]) for item in helpers)
        active_count = sum(bool(item["active_bindings"]) for item in helpers)
        business_count = sum(bool(item["business_name_hits"]) for item in helpers)
        risky_count = sum(bool(item["risky_calls"]) for item in helpers)
        family_rows.append({
            "family": family,
            "helper_count": len(helpers),
            "total_lines": total_lines,
            "presentation_hit_count": presentation_count,
            "active_binding_count": active_count,
            "business_name_count": business_count,
            "risky_call_count": risky_count,
            "start_line": helpers[0]["lineno"],
            "end_line": helpers[-1]["end_lineno"],
            "helpers": helpers,
        })

    family_rows.sort(
        key=lambda item: (
            int(item["presentation_hit_count"]),
            int(item["active_binding_count"]),
            int(item["total_lines"]),
        ),
        reverse=True,
    )
    report = {
        "desktop": DESKTOP.name,
        "line_start": LINE_START,
        "family_count": len(family_rows),
        "families": family_rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "family_count": len(family_rows),
        "top_families": [
            {
                "family": row["family"],
                "helper_count": row["helper_count"],
                "total_lines": row["total_lines"],
                "presentation_hit_count": row["presentation_hit_count"],
                "active_binding_count": row["active_binding_count"],
                "business_name_count": row["business_name_count"],
                "risky_call_count": row["risky_call_count"],
            }
            for row in family_rows[:12]
        ],
    }, ensure_ascii=True))


if __name__ == "__main__":
    main()
