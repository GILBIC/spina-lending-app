from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
COLLECTOR_MODULE = ROOT / "spina_app" / "collector_tab_presentation.py"
OUT = ROOT / "artifacts" / "wave-50-collector-route-support-boundary.json"

TARGETS = (
    "_spina_v27_route_colors",
    "_spina_v27_style_route_trees",
    "_spina_v27_route_button",
    "_spina_v27_route_card",
    "_spina_v27_update_route_cards",
    "_spina_v27_hidden_collector_widgets",
)
FORBIDDEN = (
    "connect_db(", "self.db", ".execute(", ".executemany(", ".commit(",
    ".rollback(", "run_write(", "open(", "json.load", "json.dump",
    "_write_json_atomic", "write_text(", "write_bytes(", "os.makedirs",
    "os.remove", "os.rename", "os.replace", "shutil.", "subprocess.",
    "threading.", "INSERT INTO", "UPDATE ", "DELETE FROM ",
)


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def normalized(source: str) -> str:
    return "\n".join(line.rstrip() for line in source.strip().splitlines()) + "\n"


def record(text: str, node: ast.FunctionDef) -> dict[str, object]:
    source = ast.get_source_segment(text, node)
    assert source is not None
    calls = sorted({
        dotted(call.func)
        for call in ast.walk(node)
        if isinstance(call, ast.Call) and dotted(call.func)
    })
    forbidden_hits = sorted({token for token in FORBIDDEN if token.lower() in source.lower()})
    return {
        "name": node.name,
        "lineno": node.lineno,
        "end_lineno": node.end_lineno,
        "lines": (node.end_lineno or node.lineno) - node.lineno + 1,
        "signature": ast.unparse(node.args),
        "sha256": hashlib.sha256(normalized(source).encode("utf-8")).hexdigest(),
        "calls": calls,
        "forbidden_hits": forbidden_hits,
        "source": source,
    }


def main() -> None:
    text = DESKTOP.read_text(encoding="utf-8")
    tree = ast.parse(text)
    target_records = []
    for name in TARGETS:
        matches = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name]
        assert len(matches) == 1, (name, len(matches))
        rec = record(text, matches[0])
        assert not rec["forbidden_hits"], (name, rec["forbidden_hits"])
        target_records.append(rec)

    module_text = COLLECTOR_MODULE.read_text(encoding="utf-8")
    module_tree = ast.parse(module_text)
    builder = next(
        node for node in module_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_spina_v27_build_collectors_tab"
    )
    builder_calls = sorted({
        dotted(call.func)
        for call in ast.walk(builder)
        if isinstance(call, ast.Call) and dotted(call.func)
    })
    missing_from_builder = sorted(set(TARGETS) - set(builder_calls))
    assert not missing_from_builder, missing_from_builder

    assignments = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        mentioned = sorted({
            part.id for part in ast.walk(node)
            if isinstance(part, ast.Name) and part.id in TARGETS
        })
        if mentioned:
            assignments.append({
                "lineno": getattr(node, "lineno", None),
                "mentioned": mentioned,
                "source": ast.get_source_segment(text, node) or "",
            })

    report = {
        "desktop": DESKTOP.name,
        "collector_module": str(COLLECTOR_MODULE.relative_to(ROOT)),
        "target_count": len(target_records),
        "total_target_lines": sum(int(item["lines"]) for item in target_records),
        "targets": target_records,
        "builder_calls": builder_calls,
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
