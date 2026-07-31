#!/usr/bin/env python3
"""Regression coverage for startup entry-point cleanup Wave 90."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spina_app.features.startup_runtime import install_startup_runtime

DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
HEADER = ROOT / "spina_app" / "account_header_presentation.py"


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def is_main_guard(node: ast.If) -> bool:
    test = node.test
    return (
        isinstance(test, ast.Compare)
        and isinstance(test.left, ast.Name)
        and test.left.id == "__name__"
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.Eq)
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value == "__main__"
    )


def check_architecture() -> None:
    text = DESKTOP.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(DESKTOP))

    assert not [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    ]
    assert not [
        node for node in tree.body
        if isinstance(node, ast.If)
        and is_main_guard(node)
        and len(node.body) == 1
        and isinstance(node.body[0], ast.Pass)
    ]

    final_calls = [
        node for node in tree.body
        if isinstance(node, ast.If)
        and is_main_guard(node)
        and any(
            isinstance(call, ast.Call) and dotted(call.func) == "main"
            for call in ast.walk(node)
        )
    ]
    assert len(final_calls) == 1, [node.lineno for node in final_calls]
    final_guard = final_calls[0]
    assert tree.body[-1] is final_guard, (tree.body[-1].lineno, final_guard.lineno)

    assert text.count("# --- Legacy desktop main implementation removed Wave 90 ---") == 1
    assert text.count("# --- Placeholder entry point removed Wave 90 ---") == 2
    assert text.count("_wave46_configure_account_header_dependencies(globals())") == 1
    assert text.index("_wave46_configure_account_header_dependencies(globals())") < text.index(
        "if __name__ == '__main__':\n    main()"
    )
    assert text.index("_wave82_install_data_bank_feature(") < text.index(
        "if __name__ == '__main__':\n    main()"
    )

    header = HEADER.read_text(encoding="utf-8")
    assert "install_startup_runtime(namespace)" in header


def check_runtime_install_without_legacy_main() -> None:
    events: list[str] = []

    class Root:
        def mainloop(self):
            events.append("mainloop")

    class App:
        def __init__(self, root):
            events.append("app")

    namespace: dict[str, object] = {"App": App}
    assert install_startup_runtime(namespace, root_factory=Root)
    assert namespace["_spina_startup_runtime_wave89_original_main"] is None
    installed = namespace["main"]
    assert callable(installed)
    assert installed() is not None
    assert events == ["app", "mainloop"]


def main() -> None:
    check_architecture()
    check_runtime_install_without_legacy_main()
    print("Wave 90 startup cleanup regression passed.")


if __name__ == "__main__":
    main()
