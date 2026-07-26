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


def assignment_targets(node: ast.AST) -> set[str]:
    result: set[str] = set()
    targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
    for target in targets:
        for part in ast.walk(target):
            if isinstance(part, ast.Name):
                result.add(part.id)
            elif isinstance(part, ast.Attribute):
                name = dotted(part)
                if name:
                    result.add(name)
    return result


def main() -> None:
    text = DESKTOP.read_text(encoding="utf-8")
    tree = ast.parse(text)

    definitions: dict[str, list[dict[str, object]]] = {name: [] for name in TARGETS}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in definitions:
            definitions[node.name].append(record(text, node))

    imports = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        aliases = []
        for alias in node.names:
            visible = alias.asname or alias.name
            if alias.name in TARGETS or visible in TARGETS:
                aliases.append({"name": alias.name, "asname": alias.asname, "visible": visible})
        if aliases:
            imports.append({"lineno": node.lineno, "module": node.module, "aliases": aliases})

    assignments = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = sorted(assignment_targets(node))
        mentioned_targets = sorted({name for name in TARGETS if name in targets})
        mentioned_values = sorted({
            part.id for part in ast.walk(node)
            if isinstance(part, ast.Name) and part.id in TARGETS
        })
        if mentioned_targets or mentioned_values:
            assignments.append({
                "lineno": getattr(node, "lineno", None),
                "targets": targets,
                "mentioned_targets": mentioned_targets,
                "mentioned_values": mentioned_values,
                "source": ast.get_source_segment(text, node) or "",
            })

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

    resolution = {}
    for name in TARGETS:
        records = definitions[name]
        bad = [item for item in records if item["forbidden_hits"]]
        resolution[name] = {
            "definition_count": len(records),
            "definitions": records,
            "forbidden_definition_count": len(bad),
            "used_by_active_builder": name in builder_calls,
            "import_rows": [row for row in imports if any(alias["visible"] == name or alias["name"] == name for alias in row["aliases"])],
            "assignment_rows": [row for row in assignments if name in row["mentioned_targets"] or name in row["mentioned_values"]],
        }

    report = {
        "desktop": DESKTOP.name,
        "collector_module": str(COLLECTOR_MODULE.relative_to(ROOT)),
        "targets": list(TARGETS),
        "builder_calls": builder_calls,
        "resolution": resolution,
        "imports": imports,
        "assignments": sorted(assignments, key=lambda item: int(item["lineno"] or 0)),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        name: {
            "definitions": resolution[name]["definition_count"],
            "imports": len(resolution[name]["import_rows"]),
            "assignments": len(resolution[name]["assignment_rows"]),
            "used": resolution[name]["used_by_active_builder"],
        }
        for name in TARGETS
    }, ensure_ascii=True))


if __name__ == "__main__":
    main()
