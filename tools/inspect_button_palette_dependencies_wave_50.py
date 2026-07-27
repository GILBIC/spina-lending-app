from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
UI_CONTROLS = ROOT / "spina_app" / "ui_controls.py"
THEME_PALETTES = ROOT / "spina_app" / "theme_palettes.py"
OUT = ROOT / "artifacts" / "wave-50-button-palette-dependencies.json"

NAMES = (
    "_spina_v25_collector_colors",
    "_spina_v27_route_colors",
    "_spina_v32_login_colors",
)


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def inspect_file(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    definitions = {
        name: [
            {
                "lineno": node.lineno,
                "end_lineno": node.end_lineno,
                "signature": ast.unparse(node.args),
                "source": ast.get_source_segment(text, node) or "",
            }
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == name
        ]
        for name in NAMES
    }
    imports = []
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom):
            continue
        aliases = []
        for alias in node.names:
            visible = alias.asname or alias.name
            if alias.name in NAMES or visible in NAMES:
                aliases.append({"name": alias.name, "asname": alias.asname, "visible": visible})
        if aliases:
            imports.append({"lineno": node.lineno, "module": node.module, "aliases": aliases})
    assignments = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        target_names = sorted({dotted(target) for target in targets if dotted(target)})
        names = sorted({part.id for part in ast.walk(node) if isinstance(part, ast.Name) and part.id in NAMES})
        if names or any(name in target_names for name in NAMES):
            assignments.append({
                "lineno": getattr(node, "lineno", None),
                "targets": target_names,
                "names": names,
                "value": ast.unparse(node.value),
                "source": ast.get_source_segment(text, node) or "",
            })
    return {
        "path": str(path.relative_to(ROOT)),
        "definitions": definitions,
        "imports": imports,
        "assignments": sorted(assignments, key=lambda item: int(item["lineno"] or 0)),
    }


def main() -> None:
    report = {
        "desktop": inspect_file(DESKTOP),
        "ui_controls": inspect_file(UI_CONTROLS),
        "theme_palettes": inspect_file(THEME_PALETTES),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    summary = {}
    for section, data in report.items():
        summary[section] = {
            name: {
                "definitions": len(data["definitions"][name]),
                "imports": sum(1 for row in data["imports"] for alias in row["aliases"] if alias["name"] == name or alias["visible"] == name),
                "assignments": sum(1 for row in data["assignments"] if name in row["names"] or name in row["targets"]),
            }
            for name in NAMES
        }
    print(json.dumps(summary, ensure_ascii=True))


if __name__ == "__main__":
    main()
