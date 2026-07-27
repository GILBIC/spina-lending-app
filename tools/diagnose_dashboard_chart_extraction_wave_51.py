from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
BRIDGE = ROOT / "spina_app" / "tabs" / "dashboard.py"
MODULE = ROOT / "spina_app" / "dashboard_chart_presentation.py"
OUT = ROOT / "artifacts" / "wave-51-extraction-diagnostics.json"
TARGETS = (
    "_spina_v18_draw_dashboard_charts",
    "_spina_v20_fix_chart_titles",
    "_spina_v20_draw_dashboard_charts",
)
DEPENDENCIES = (
    "_log_exc",
    "_spina_v18_dashboard_palette",
    "_spina_v18_draw_round_rect",
    "_spina_v18_fmt_money_compact",
    "_spina_v18_patch_dashboard_chart_cards",
    "_spina_v20_dash_palette",
    "_spina_v20_money",
    "_spina_v20_round_rect",
)
BRIDGE_TARGETS = (
    "configure_legacy_dashboard_feature",
    "_spina_v18_draw_dashboard_charts",
    "_spina_v20_draw_dashboard_charts",
)


def normalized(source: str) -> str:
    return "\n".join(line.rstrip() for line in source.strip().splitlines()) + "\n"


def sha(source: str) -> str:
    return hashlib.sha256(normalized(source).encode("utf-8")).hexdigest()


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def source_for(text: str, node: ast.AST) -> str:
    return ast.get_source_segment(text, node) or ""


def top_level_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                for part in ast.walk(target):
                    if isinstance(part, ast.Name):
                        names.add(part.id)
        elif isinstance(node, ast.AnnAssign):
            for part in ast.walk(node.target):
                if isinstance(part, ast.Name):
                    names.add(part.id)
    return names


def main() -> None:
    desktop_text = DESKTOP.read_text(encoding="utf-8")
    desktop_tree = ast.parse(desktop_text)
    bridge_text = BRIDGE.read_text(encoding="utf-8")
    bridge_tree = ast.parse(bridge_text)

    functions = {}
    for name in TARGETS:
        matches = [node for node in desktop_tree.body if isinstance(node, ast.FunctionDef) and node.name == name]
        if len(matches) != 1:
            functions[name] = {"count": len(matches)}
            continue
        node = matches[0]
        source = source_for(desktop_text, node)
        functions[name] = {
            "count": 1,
            "lineno": node.lineno,
            "end_lineno": node.end_lineno,
            "lines": (node.end_lineno or node.lineno) - node.lineno + 1,
            "signature": ast.unparse(node.args),
            "sha256": sha(source),
            "calls": sorted({
                dotted(call.func)
                for call in ast.walk(node)
                if isinstance(call, ast.Call) and dotted(call.func)
            }),
        }

    names = top_level_names(desktop_tree)
    dependency_status = {name: name in names for name in DEPENDENCIES}

    bridge_functions = {}
    for name in BRIDGE_TARGETS:
        matches = [node for node in bridge_tree.body if isinstance(node, ast.FunctionDef) and node.name == name]
        bridge_functions[name] = {
            "count": len(matches),
            "sha256": sha(source_for(bridge_text, matches[0])) if len(matches) == 1 else None,
            "lineno": matches[0].lineno if len(matches) == 1 else None,
        }

    bridge_calls = []
    for call in (node for node in ast.walk(desktop_tree) if isinstance(node, ast.Call)):
        fn = dotted(call.func)
        if "configure_legacy_dashboard_feature" not in fn:
            continue
        bridge_calls.append({
            "lineno": call.lineno,
            "function": fn,
            "keywords": {item.arg: dotted(item.value) for item in call.keywords if item.arg},
        })

    report = {
        "module_exists": MODULE.exists(),
        "desktop_functions": functions,
        "dependency_status": dependency_status,
        "missing_dependencies": [name for name, present in dependency_status.items() if not present],
        "bridge_functions": bridge_functions,
        "bridge_calls": bridge_calls,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, separators=(",", ":")))


if __name__ == "__main__":
    main()
