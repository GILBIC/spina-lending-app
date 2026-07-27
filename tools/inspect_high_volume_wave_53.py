from __future__ import annotations

import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
REPORT = ROOT / "artifacts" / "wave-53-candidates.txt"

TARGETS = (
    "_spina_cashctl_build_tab",
    "_spina_v21_cash_refresh",
    "_spina_perf_refresh_data_grid",
    "_build_clients_tab",
    "_show_import_log_window",
    "_build_reports_tab",
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


def find_target(tree: ast.Module, name: str) -> tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return "module", node
        if isinstance(node, ast.ClassDef) and node.name == "App":
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == name:
                    return "App", child
    raise KeyError(name)


def assignments(tree: ast.Module, name: str) -> list[str]:
    rows: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Name) or node.value.id != name:
            continue
        for target in node.targets:
            rendered = dotted(target)
            if rendered:
                rows.append(f"line {node.lineno}: {rendered} = {name}")
    return sorted(set(rows))


def external_loads(tree: ast.Module, target: ast.AST, name: str) -> list[str]:
    rows: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Name) or not isinstance(node.ctx, ast.Load) or node.id != name:
            continue
        if target.lineno <= node.lineno <= target.end_lineno:
            continue
        rows.append(f"line {node.lineno}")
    return sorted(set(rows))


def main() -> None:
    text = DESKTOP.read_text(encoding="utf-8")
    tree = ast.parse(text)
    rows: list[str] = []

    for name in TARGETS:
        owner, node = find_target(tree, name)
        source = ast.get_source_segment(text, node)
        assert source is not None
        calls = sorted({dotted(sub.func) for sub in ast.walk(node) if isinstance(sub, ast.Call) and dotted(sub.func)})
        attrs = sorted({dotted(sub) for sub in ast.walk(node) if isinstance(sub, ast.Attribute) and dotted(sub)})
        rows.extend(
            [
                "=" * 100,
                f"TARGET: {name}",
                f"OWNER: {owner}",
                f"LINES: {node.lineno}-{node.end_lineno} ({node.end_lineno - node.lineno + 1})",
                f"SHA256: {hashlib.sha256(normalized(source).encode('utf-8')).hexdigest()}",
                "ASSIGNMENTS:",
                *(assignments(tree, name) or ["- none"]),
                "EXTERNAL LOADS:",
                *(external_loads(tree, node, name) or ["- none"]),
                "CALLS:",
                *(f"- {call}" for call in calls),
                "SELF/APP ATTRIBUTES:",
                *(f"- {attr}" for attr in attrs if attr.startswith("self.") or attr.startswith("App.")),
                "SOURCE:",
                source,
                "",
            ]
        )

    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text("\n".join(rows), encoding="utf-8")
    print(f"Wrote {REPORT} with {len(TARGETS)} candidate boundaries.")


if __name__ == "__main__":
    main()
