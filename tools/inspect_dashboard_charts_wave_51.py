from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
OUT = ROOT / "artifacts" / "wave-51-dashboard-chart-boundary.json"

TARGETS = {
    "_spina_v18_draw_dashboard_charts",
    "_spina_v20_draw_dashboard_charts",
}
RANGE_START = 34800
RANGE_END = 35680
HARD_TOKENS = (
    "connect_db(", "run_write(", ".execute(", ".executemany(", ".commit(",
    ".rollback(", "insert into", "delete from", "open(", "json.load",
    "json.dump", ".write_text(", ".read_text(", "os.remove", "os.replace",
    "subprocess.", "threading.", "reportlab", "filedialog.",
)


def normalized(source: str) -> str:
    return "\n".join(line.rstrip() for line in source.strip().splitlines()) + "\n"


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def describe(text: str, node: ast.FunctionDef) -> dict[str, object]:
    source = ast.get_source_segment(text, node) or ""
    calls = sorted({
        dotted(call.func)
        for call in ast.walk(node)
        if isinstance(call, ast.Call) and dotted(call.func)
    })
    assigned_attrs = sorted({
        dotted(target)
        for part in ast.walk(node)
        if isinstance(part, (ast.Assign, ast.AnnAssign, ast.AugAssign))
        for target in (
            list(part.targets) if isinstance(part, ast.Assign)
            else [part.target]
        )
        if dotted(target)
    })
    lower = source.lower()
    return {
        "name": node.name,
        "lineno": node.lineno,
        "end_lineno": node.end_lineno,
        "lines": (node.end_lineno or node.lineno) - node.lineno + 1,
        "signature": ast.unparse(node.args),
        "sha256": hashlib.sha256(normalized(source).encode("utf-8")).hexdigest(),
        "calls": calls,
        "assigned_attributes": assigned_attrs,
        "hard_hits": sorted({token for token in HARD_TOKENS if token.lower() in lower}),
        "source": source,
    }


def main() -> None:
    text = DESKTOP.read_text(encoding="utf-8")
    tree = ast.parse(text)
    functions = [
        describe(text, node)
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and (
            node.name in TARGETS
            or RANGE_START <= node.lineno <= RANGE_END
            or "dashboard" in node.name.lower()
        )
    ]

    assignments = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        source = ast.get_source_segment(text, node) or ""
        names = sorted({
            part.id
            for part in ast.walk(node)
            if isinstance(part, ast.Name) and part.id in TARGETS
        })
        app_attrs = sorted({
            part.attr
            for part in ast.walk(node)
            if isinstance(part, ast.Attribute)
            and isinstance(part.value, ast.Name)
            and part.value.id == "App"
            and "dashboard" in part.attr.lower()
        })
        if names or app_attrs:
            assignments.append({
                "lineno": getattr(node, "lineno", None),
                "names": names,
                "app_attributes": app_attrs,
                "source": source,
            })

    definitions_by_file = {}
    references_by_file = {}
    for path in sorted(ROOT.rglob("*.py")):
        if any(part in {".git", "__pycache__", ".venv", "venv"} for part in path.parts):
            continue
        try:
            file_text = path.read_text(encoding="utf-8")
            file_tree = ast.parse(file_text)
        except Exception:
            continue
        defs = sorted({
            node.name for node in file_tree.body
            if isinstance(node, ast.FunctionDef) and node.name in TARGETS
        })
        refs = sorted({
            node.id for node in ast.walk(file_tree)
            if isinstance(node, ast.Name) and node.id in TARGETS
        })
        if defs:
            definitions_by_file[str(path.relative_to(ROOT))] = defs
        if refs:
            references_by_file[str(path.relative_to(ROOT))] = refs

    report = {
        "desktop": DESKTOP.name,
        "range": [RANGE_START, RANGE_END],
        "targets": sorted(TARGETS),
        "functions": functions,
        "assignments": sorted(assignments, key=lambda item: int(item["lineno"] or 0)),
        "definitions_by_file": definitions_by_file,
        "references_by_file": references_by_file,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "functions": [
            {"name": item["name"], "lines": item["lines"], "hard_hits": item["hard_hits"]}
            for item in functions
        ],
        "assignments": report["assignments"],
        "definitions_by_file": definitions_by_file,
    }, ensure_ascii=True))


if __name__ == "__main__":
    main()
