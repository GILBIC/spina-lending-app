from __future__ import annotations

import ast
from pathlib import Path

APP_PATH = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
OUT_PATH = Path("docs/wave-62-delete-day-source.tmp.txt")
TARGET = "open_delete_day_dialog"


def main() -> None:
    text = APP_PATH.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text)
    app = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    method = next(
        node for node in app.body
        if isinstance(node, ast.FunctionDef) and node.name == TARGET
    )
    source = "".join(lines[method.lineno - 1:method.end_lineno])
    span = method.end_lineno - method.lineno + 1
    if span != 141:
        raise SystemExit(f"Expected 141 lines, found {span}")
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(source, encoding="utf-8")
    print(f"Wrote {span} exact source lines to {OUT_PATH}")


if __name__ == "__main__":
    main()
