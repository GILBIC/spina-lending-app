from __future__ import annotations

import ast
import json
from pathlib import Path

APP = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
OUTPUT = Path("tools/fixtures/area_ui_phase2_inspection.json")

MARKERS = (
    "open_areas_manager",
    "self.area_var = tk.StringVar",
    "area_var = tk.StringVar",
    "self.area_cb = ttk.Combobox",
    "area_cb = ttk.Combobox",
    "Area / Route",
    "_add_area_quick",
    "simpledialog.askstring('Add Area'",
    'simpledialog.askstring("Add Area"',
    "ensure_area_exists",
)


def _owner_map(tree: ast.AST) -> dict[int, str]:
    owners: dict[int, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    owners[id(child)] = node.name
    return owners


def _contexts(source_lines: list[str], node: ast.AST) -> list[dict[str, object]]:
    start = int(getattr(node, "lineno", 1))
    end = int(getattr(node, "end_lineno", start))
    found: list[dict[str, object]] = []
    for lineno in range(start, end + 1):
        text = source_lines[lineno - 1]
        if not any(marker in text for marker in MARKERS):
            continue
        context_start = max(start, lineno - 12)
        context_end = min(end, lineno + 18)
        block = "\n".join(
            f"{n}: {source_lines[n - 1]}" for n in range(context_start, context_end + 1)
        )
        found.append(
            {
                "match_line": lineno,
                "start_line": context_start,
                "end_line": context_end,
                "text": block,
            }
        )
    return found


def main() -> None:
    source = APP.read_text(encoding="utf-8")
    source_lines = source.splitlines()
    tree = ast.parse(source, filename=str(APP))
    owners = _owner_map(tree)

    results: list[dict[str, object]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        exact = ast.get_source_segment(source, node) or ""
        if not any(marker in exact for marker in MARKERS):
            continue
        contexts = _contexts(source_lines, node)
        if not contexts:
            continue
        results.append(
            {
                "owner": owners.get(id(node), ""),
                "name": node.name,
                "line": node.lineno,
                "end_line": node.end_lineno,
                "signature": ast.unparse(node.args),
                "contexts": contexts,
            }
        )

    results.sort(key=lambda item: (int(item["line"]), str(item["name"])))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps({"app": str(APP), "functions": results}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Recorded {len(results)} focused Area UI functions")


if __name__ == "__main__":
    main()
