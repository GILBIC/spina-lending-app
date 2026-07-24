"""Record exact Wave 29 method bodies and runtime wiring contexts."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from tools.inventory_navigation_databank_shell_wave_29 import GROUPS, SOURCE, TARGETS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "navigation-databank-shell-wave-29-sources.json"


def segment(lines: list[str], node: ast.AST) -> str:
    return "\n".join(lines[node.lineno - 1 : node.end_lineno])


def assignment_targets(node: ast.Assign | ast.AnnAssign) -> list[ast.AST]:
    return node.targets if isinstance(node, ast.Assign) else [node.target]


def main() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    lines = text.splitlines()
    tree = ast.parse(text, filename=str(SOURCE))
    app = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    methods = {
        node.name: node
        for node in app.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in TARGETS
    }
    assert set(methods) == set(TARGETS)

    assignments: dict[str, list[dict[str, object]]] = {name: [] for name in TARGETS}
    target_set = set(TARGETS)
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            for target in assignment_targets(node):
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "App"
                    and target.attr in target_set
                ):
                    assignments[target.attr].append(
                        {
                            "line": node.lineno,
                            "source": segment(lines, node),
                        }
                    )

    imports = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            rendered = segment(lines, node)
            if "spina_app" in rendered:
                imports.append({"line": node.lineno, "source": rendered})

    main_guards = []
    for node in tree.body:
        if isinstance(node, ast.If):
            rendered_test = ast.unparse(node.test)
            if "__name__" in rendered_test and "__main__" in rendered_test:
                main_guards.append({"line": node.lineno, "source": segment(lines, node)})

    report = {
        "app_start_line": app.lineno,
        "app_end_line": app.end_lineno,
        "methods": {
            group: [
                {
                    "name": name,
                    "start_line": methods[name].lineno,
                    "end_line": methods[name].end_lineno,
                    "source": segment(lines, methods[name]),
                    "app_assignments": assignments[name],
                }
                for name in names
            ]
            for group, names in GROUPS.items()
        },
        "spina_imports": imports,
        "main_guards": main_guards,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("Wave 29 exact source inspection passed:", len(TARGETS), "methods")


if __name__ == "__main__":
    main()
