#!/usr/bin/env python3
"""Permanent read-only startup architecture guard for Wave 91."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
WORKFLOW = ROOT / ".github" / "workflows" / "startup-cleanup-wave-90.yml"
GENERATOR = ROOT / "tools" / "apply_startup_cleanup_wave_90.py"
RUNTIME = ROOT / "spina_app" / "features" / "startup_runtime.py"


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


def check_desktop_entry_point() -> None:
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

    final_guards = [
        node for node in tree.body
        if isinstance(node, ast.If)
        and is_main_guard(node)
        and any(
            isinstance(call, ast.Call) and dotted(call.func) == "main"
            for call in ast.walk(node)
        )
    ]
    assert len(final_guards) == 1, [node.lineno for node in final_guards]
    assert text.count("# --- Legacy desktop main implementation removed Wave 90 ---") == 1
    assert text.count("# --- Placeholder entry point removed Wave 90 ---") == 2


def check_read_only_workflow() -> None:
    assert not GENERATOR.exists(), "temporary Wave 90 generator returned"
    workflow = WORKFLOW.read_text(encoding="utf-8")
    lowered = workflow.lower()

    assert workflow.startswith("name: Startup architecture validation Wave 91\n")
    assert "contents: read" in workflow
    assert "contents: write" not in workflow
    assert "persist-credentials: false" in workflow
    assert "persist-credentials: true" not in workflow
    assert "apply_startup_cleanup_wave_90.py" not in workflow
    assert "git push" not in lowered
    assert "git commit" not in lowered
    assert "git add" not in lowered
    assert "github-actions[bot]" not in lowered
    assert "Commit validated cleanup" not in workflow
    assert "Apply obsolete startup cleanup" not in workflow
    assert "Check generated diff" not in workflow
    assert "Require clean committed tree" in workflow
    assert "tools\\test_startup_validation_wave_91.py" in workflow


def check_runtime_owner() -> None:
    text = RUNTIME.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(RUNTIME))
    names = {
        node.name for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }
    assert {"run_desktop_application", "install_startup_runtime"} <= names
    assert 'namespace["main"] = main' in text
    assert 'namespace["_spina_startup_runtime_wave89_installed"] = True' in text


def main() -> None:
    check_desktop_entry_point()
    check_read_only_workflow()
    check_runtime_owner()
    print("Wave 91 permanent startup validation guard passed.")


if __name__ == "__main__":
    main()
