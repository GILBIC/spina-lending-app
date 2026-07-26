from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
OUT = ROOT / "artifacts" / "wave-48-side-navigation-boundary.json"

TARGETS = (
    "_spina_v13_hide_main_notebook_tabs",
    "_spina_v13_side_nav_items",
    "_spina_v13_rebuild_side_nav",
    "_spina_v13_refresh_side_nav_selection",
    "_spina_v13_setup_style",
    "_spina_v13_apply_ui_theme",
)
PROTECTED_NEIGHBORS = (
    "_spina_v13_app_init",
    "_spina_v13_apply_role_access",
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


def function_nodes(tree: ast.AST, name: str) -> list[ast.FunctionDef]:
    return [
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]


def record(text: str, node: ast.FunctionDef) -> dict[str, object]:
    source = ast.get_source_segment(text, node)
    assert source is not None
    calls = sorted({
        dotted(call.func)
        for call in ast.walk(node)
        if isinstance(call, ast.Call) and dotted(call.func)
    })
    loads = sorted({
        part.id
        for part in ast.walk(node)
        if isinstance(part, ast.Name) and isinstance(part.ctx, ast.Load)
    })
    stores = sorted({
        dotted(part) if isinstance(part, ast.Attribute) else part.id
        for part in ast.walk(node)
        if (
            isinstance(part, ast.Name) and isinstance(part.ctx, ast.Store)
        ) or (
            isinstance(part, ast.Attribute) and isinstance(part.ctx, ast.Store)
        )
    })
    return {
        "name": node.name,
        "lineno": node.lineno,
        "end_lineno": node.end_lineno,
        "lines": (node.end_lineno or node.lineno) - node.lineno + 1,
        "signature": ast.unparse(node.args),
        "sha256": normalized_hash(source),
        "calls": calls,
        "loads": loads,
        "stores": stores,
        "source": source,
    }


def main() -> None:
    text = DESKTOP.read_text(encoding="utf-8")
    tree = ast.parse(text)
    targets = []
    for name in TARGETS:
        matches = function_nodes(tree, name)
        assert len(matches) == 1, (name, len(matches))
        targets.append(record(text, matches[0]))

    neighbors = []
    for name in PROTECTED_NEIGHBORS:
        matches = function_nodes(tree, name)
        assert len(matches) == 1, (name, len(matches))
        neighbors.append(record(text, matches[0]))

    names = set(TARGETS) | set(PROTECTED_NEIGHBORS)
    assignments = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        mentioned = {
            part.id for part in ast.walk(node)
            if isinstance(part, ast.Name) and part.id in names
        }
        if not mentioned:
            continue
        assignments.append({
            "lineno": getattr(node, "lineno", None),
            "mentioned": sorted(mentioned),
            "source": ast.get_source_segment(text, node) or "",
        })

    report = {
        "desktop": DESKTOP.name,
        "target_count": len(targets),
        "total_target_lines": sum(int(item["lines"]) for item in targets),
        "targets": targets,
        "protected_neighbors": neighbors,
        "assignments": sorted(assignments, key=lambda item: int(item["lineno"] or 0)),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "target_count": report["target_count"],
        "total_target_lines": report["total_target_lines"],
        "target_names": list(TARGETS),
    }, ensure_ascii=True))


if __name__ == "__main__":
    main()
