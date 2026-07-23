from __future__ import annotations

import ast
import json
import re
from pathlib import Path

APP = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
OUTPUT = Path("tools/fixtures/hierarchical_area_focus.json")

PATTERNS = {
    "client_area_controls": [
        r"area_var", r"area_entry", r"area_cmb", r"area_combo", r"sub_area",
        r"client[^\n]{0,80}area", r"area[^\n]{0,80}client",
    ],
    "client_sql": [
        r"CREATE TABLE[^\n]{0,200}clients", r"ALTER TABLE[^\n]{0,200}clients",
        r"INSERT INTO clients", r"UPDATE clients", r"SELECT[^\n]{0,200}\barea\b[^\n]{0,200}FROM clients",
    ],
    "collector_area": [
        r"collectors\.json", r"collector[^\n]{0,100}areas", r"areas[^\n]{0,100}collector",
        r"collector_route_filter_main", r"_collectors_move_area",
    ],
    "databank_area": [
        r"data bank", r"databank", r"SELECT DISTINCT area", r"GROUP BY area", r"ORDER BY area",
    ],
    "ordering_and_preferences": [
        r"areas_order", r"ledger_prefs\.json", r"resolve_area_order_from_prefs",
    ],
}


def excerpt(lines: list[str], line_number: int, radius: int = 4) -> dict[str, object]:
    start = max(1, line_number - radius)
    end = min(len(lines), line_number + radius)
    return {
        "line": line_number,
        "start_line": start,
        "end_line": end,
        "text": "\n".join(f"{i}: {lines[i - 1]}" for i in range(start, end + 1)),
    }


def function_records(tree: ast.AST, source: str) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    keywords = (
        "area", "client", "collector", "databank", "ledger", "route",
        "filter", "order", "edit", "save", "add", "update", "migration",
    )
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        segment = ast.get_source_segment(source, node) or ""
        lower = segment.lower()
        if "area" not in lower:
            continue
        name_lower = node.name.lower()
        if not any(word in name_lower or word in lower[:1000] for word in keywords):
            continue
        matches = []
        for category, patterns in PATTERNS.items():
            if any(re.search(pattern, segment, flags=re.IGNORECASE | re.DOTALL) for pattern in patterns):
                matches.append(category)
        if not matches and len(segment.splitlines()) > 220:
            continue
        records.append({
            "name": node.name,
            "line": node.lineno,
            "end_line": node.end_lineno,
            "line_count": (node.end_lineno or node.lineno) - node.lineno + 1,
            "categories": sorted(matches),
            "signature": ast.unparse(node.args),
        })
    records.sort(key=lambda item: (0 if item["categories"] else 1, item["line_count"], item["line"]))
    return records[:120]


def sql_records(tree: ast.AST) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        text = node.value
        lower = text.lower()
        if "area" not in lower:
            continue
        if not any(token in lower for token in ("select", "insert", "update", "alter", "create table", "delete")):
            continue
        compact = " ".join(text.split())
        out.append({
            "line": getattr(node, "lineno", None),
            "sql": compact[:1200],
        })
    out.sort(key=lambda item: (item["line"] or 0, item["sql"]))
    return out[:180]


def main() -> None:
    source = APP.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source, filename=str(APP))

    occurrences: dict[str, list[dict[str, object]]] = {}
    for category, patterns in PATTERNS.items():
        found: list[dict[str, object]] = []
        seen: set[int] = set()
        for pattern in patterns:
            regex = re.compile(pattern, flags=re.IGNORECASE)
            for index, line in enumerate(lines, start=1):
                if regex.search(line) and index not in seen:
                    found.append(excerpt(lines, index))
                    seen.add(index)
                    if len(found) >= 80:
                        break
            if len(found) >= 80:
                break
        occurrences[category] = found

    result = {
        "app": str(APP),
        "line_count": len(lines),
        "occurrences": occurrences,
        "functions": function_records(tree, source),
        "sql": sql_records(tree),
    }
    OUTPUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        "Focused area report: "
        f"functions={len(result['functions'])}, sql={len(result['sql'])}, "
        f"occurrences={sum(len(v) for v in occurrences.values())}"
    )


if __name__ == "__main__":
    main()
