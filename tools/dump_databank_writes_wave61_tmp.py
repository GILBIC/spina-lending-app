from __future__ import annotations

import ast
from pathlib import Path

APP = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
OUT = Path("docs/wave-61-write-source.tmp.txt")
TARGETS = ("_save_cell_edit", "delete_selected_cell", "_mark_missed_for_selected")


def main() -> None:
    text = APP.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text)
    app_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    methods = {node.name: node for node in app_class.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    chunks = []
    for name in TARGETS:
        node = methods[name]
        source = "".join(lines[node.lineno - 1 : node.end_lineno])
        chunks.append(f"===== {name} lines {node.lineno}-{node.end_lineno} =====\n{source}\n")
    OUT.write_text("\n".join(chunks), encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
