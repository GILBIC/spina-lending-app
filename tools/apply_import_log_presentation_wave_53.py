from __future__ import annotations

import ast
import hashlib
import textwrap
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "import_log_presentation.py"
DIAGNOSTIC = ROOT / "tools" / "wave53_diagnostic.txt"

TARGET = "_show_import_log_window"
EXPECTED_LINES = 337
EXPECTED_SHA256 = "017ec81edcd4d086f905ce5a147a0a0855073f354ed63955d171aa15ed22c912"
ALIAS = "_wave53_show_import_log_window"
CONFIG_ALIAS = "_configure_wave53_import_log"


def normalized(source: str) -> str:
    return "\n".join(line.rstrip() for line in textwrap.dedent(source).strip().splitlines()) + "\n"


def line_offsets(text: str) -> list[int]:
    offsets = [0]
    for line in text.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    return offsets


def replacement_span(text: str, node: ast.AST) -> tuple[int, int]:
    offsets = line_offsets(text)
    start = offsets[node.lineno - 1]
    end = offsets[node.end_lineno]
    while end < len(text) and text[end] in "\r\n":
        end += 1
    return start, end


def enclosing_function_names(tree: ast.Module) -> tuple[str, ...]:
    names: set[str] = set()

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.stack: list[str] = []

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self.stack.append(node.name)
            for child in node.body:
                self.visit(child)
            self.stack.pop()

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Call(self, node: ast.Call) -> None:
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == TARGET:
                names.add(".".join(self.stack) or "<module>")
            self.generic_visit(node)

    Visitor().visit(tree)
    return tuple(sorted(names))


def find_app_method(tree: ast.Module) -> tuple[ast.ClassDef, ast.FunctionDef]:
    app_classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "App"]
    if len(app_classes) != 1:
        raise AssertionError(("App classes", len(app_classes)))
    app = app_classes[0]
    methods = [node for node in app.body if isinstance(node, ast.FunctionDef) and node.name == TARGET]
    if len(methods) != 1:
        raise AssertionError((TARGET, len(methods)))
    return app, methods[0]


def final_main_guard(tree: ast.Module) -> ast.If:
    guards: list[ast.If] = []
    for node in tree.body:
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if not isinstance(test, ast.Compare) or len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
            continue
        if not isinstance(test.left, ast.Name) or test.left.id != "__name__":
            continue
        if len(test.comparators) != 1:
            continue
        comp = test.comparators[0]
        if isinstance(comp, ast.Constant) and comp.value == "__main__":
            guards.append(node)
    if not guards:
        raise AssertionError("No __main__ guard found")
    return guards[-1]


def build_module(source: str, callers: tuple[str, ...]) -> str:
    callers_repr = repr(callers)
    return f'''from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, ttk

IMPORT_LOG_TARGET = {TARGET!r}
IMPORT_LOG_SOURCE_LINES = {EXPECTED_LINES}
IMPORT_LOG_SOURCE_SHA256 = {EXPECTED_SHA256!r}
IMPORT_LOG_CALLERS = {callers_repr}

_log_suppressed_once = None
_open_path = None
DATA_DIR = None


def configure_import_log_dependencies(namespace) -> None:
    global _log_suppressed_once, _open_path, DATA_DIR
    _log_suppressed_once = namespace["_log_suppressed_once"]
    _open_path = namespace["_open_path"]
    DATA_DIR = namespace["DATA_DIR"]


{normalized(source)}'''


def binding_block() -> str:
    return f'''# Wave 53: active Import Log viewer presentation extraction.
from spina_app.import_log_presentation import (
    configure_import_log_dependencies as {CONFIG_ALIAS},
    {TARGET} as {ALIAS},
)
{CONFIG_ALIAS}(globals())
App.{TARGET} = {ALIAS}


'''


def apply() -> None:
    text = DESKTOP.read_text(encoding="utf-8")
    tree = ast.parse(text)
    _app, method = find_app_method(tree)
    source = ast.get_source_segment(text, method)
    if source is None:
        raise AssertionError("Could not recover import-log source")
    if method.end_lineno - method.lineno + 1 != EXPECTED_LINES:
        raise AssertionError(("source lines", method.end_lineno - method.lineno + 1))
    digest = hashlib.sha256(normalized(source).encode("utf-8")).hexdigest()
    if digest != EXPECTED_SHA256:
        raise AssertionError(("source sha256", digest))

    callers = enclosing_function_names(tree)
    if not callers:
        raise AssertionError("Import-log viewer has no active callers")

    start, end = replacement_span(text, method)
    without_method = text[:start] + text[end:]
    without_tree = ast.parse(without_method)
    guard = final_main_guard(without_tree)
    offsets = line_offsets(without_method)
    insert_at = offsets[guard.lineno - 1]
    updated = without_method[:insert_at] + binding_block() + without_method[insert_at:]
    updated_tree = ast.parse(updated)

    _app_after, methods_after = None, []
    for node in updated_tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "App":
            _app_after = node
            methods_after = [child for child in node.body if isinstance(child, ast.FunctionDef) and child.name == TARGET]
            break
    if _app_after is None or methods_after:
        raise AssertionError("Original App import-log method survived extraction")

    bindings = []
    for node in updated_tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "App"
            and target.attr == TARGET
            and isinstance(node.value, ast.Name)
        ):
            bindings.append(node.value.id)
    if bindings != [ALIAS]:
        raise AssertionError(("bindings", bindings))

    MODULE.write_text(build_module(source, callers), encoding="utf-8")
    ast.parse(MODULE.read_text(encoding="utf-8"))
    DESKTOP.write_text(updated, encoding="utf-8")
    print(
        f"Wave 53 extraction applied: {EXPECTED_LINES} Import Log presentation lines moved; "
        f"callers={callers}."
    )


def main() -> None:
    apply()
    DIAGNOSTIC.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        report = traceback.format_exc()
        DIAGNOSTIC.write_text(report, encoding="utf-8")
        print(report)
        raise
