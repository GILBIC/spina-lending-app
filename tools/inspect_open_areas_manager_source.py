from __future__ import annotations

import ast
from pathlib import Path

APP = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
OUTPUT = Path("tools/fixtures/open_areas_manager_source.txt")


def main() -> None:
    source = APP.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(APP))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "open_areas_manager":
            exact = ast.get_source_segment(source, node)
            if exact is None:
                raise SystemExit("Could not recover open_areas_manager source")
            OUTPUT.parent.mkdir(parents=True, exist_ok=True)
            OUTPUT.write_text(exact + "\n", encoding="utf-8")
            print(f"Recorded open_areas_manager lines {node.lineno}-{node.end_lineno}")
            return
    raise SystemExit("open_areas_manager not found")


if __name__ == "__main__":
    main()
