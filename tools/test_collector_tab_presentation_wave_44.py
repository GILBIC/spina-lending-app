from __future__ import annotations

import ast
import hashlib
import importlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DESKTOP = ROOT / 'OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py'
MODULE_PATH = ROOT / 'spina_app/collector_tab_presentation.py'
TARGET = '_spina_v27_build_collectors_tab'
EXPECTED_LINES = 293
EXPECTED_SHA256 = '5ce718e8f43404331b044d2f3f43b81dc34b0782a15d45a317121e61da6701cb'
EXPECTED_SIGNATURE = 'self'
EXPECTED_NESTED = ['_set_sort', '_select_status', '_popup', '_on_search']
SQL_WRITE_RE = re.compile(r'\b(?:INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|REPLACE\s+INTO|ALTER\s+TABLE|DROP\s+TABLE|CREATE\s+TABLE)\b', re.I)


def normalized(text: str) -> str:
    return '\n'.join(line.rstrip() for line in text.strip().splitlines()) + '\n'


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f'{left}.{node.attr}' if left else node.attr
    return ''


def top_functions(tree: ast.Module, name: str):
    return [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name]


def source_for(lines: list[str], node: ast.AST) -> str:
    return '\n'.join(lines[node.lineno - 1:node.end_lineno])


def signature_text(fn: ast.FunctionDef) -> str:
    args = []
    pos = list(fn.args.posonlyargs) + list(fn.args.args)
    defaults = [None] * (len(pos) - len(fn.args.defaults)) + list(fn.args.defaults)
    for arg, default in zip(pos, defaults):
        args.append(arg.arg if default is None else f'{arg.arg}={ast.unparse(default)}')
    return ', '.join(args)


def main() -> None:
    module = importlib.import_module('spina_app.collector_tab_presentation')
    assert module.COLLECTOR_TAB_TARGET == TARGET
    assert module.COLLECTOR_TAB_SOURCE_LINES == EXPECTED_LINES
    assert module.COLLECTOR_TAB_SOURCE_SHA256 == EXPECTED_SHA256
    assert module.COLLECTOR_TAB_SIGNATURE == EXPECTED_SIGNATURE
    assert module.COLLECTOR_TAB_NESTED_CALLBACKS == EXPECTED_NESTED

    module_text = MODULE_PATH.read_text(encoding='utf-8')
    module_lines = module_text.splitlines()
    module_tree = ast.parse(module_text)
    module_defs = top_functions(module_tree, TARGET)
    assert len(module_defs) == 1, len(module_defs)
    fn = module_defs[0]
    fn_source = source_for(module_lines, fn)
    assert len(fn_source.splitlines()) == EXPECTED_LINES
    assert hashlib.sha256(normalized(fn_source).encode()).hexdigest() == EXPECTED_SHA256
    assert signature_text(fn) == EXPECTED_SIGNATURE
    nested = [
        node.name
        for node in sorted(
            (
                node
                for node in ast.walk(fn)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node is not fn
            ),
            key=lambda node: node.lineno,
        )
    ]
    assert nested == EXPECTED_NESTED

    calls = sorted({dotted(n.func) for n in ast.walk(fn) if isinstance(n, ast.Call) and dotted(n.func)})
    assert calls == module.COLLECTOR_TAB_CALLS
    for node in ast.walk(fn):
        if isinstance(node, ast.Attribute):
            assert not dotted(node).startswith('self.db')
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert not SQL_WRITE_RE.search(node.value)

    desktop_text = DESKTOP.read_text(encoding='utf-8')
    desktop_tree = ast.parse(desktop_text)
    assert not top_functions(desktop_tree, TARGET), 'original target still present in desktop'
    assert not top_functions(desktop_tree, '_spina_v25_build_collectors_tab')
    assert not top_functions(desktop_tree, '_spina_v25_collector_button')
    assert len(top_functions(desktop_tree, '_build_collectors_tab')) == 1

    imports = [
        n for n in desktop_tree.body
        if isinstance(n, ast.ImportFrom)
        and n.module == 'spina_app.collector_tab_presentation'
    ]
    assert len(imports) == 1
    aliases = {(a.name, a.asname) for a in imports[0].names}
    assert (TARGET, '_wave44_spina_v27_build_collectors_tab') in aliases

    rebinds = []
    runtime = []
    for node in ast.walk(desktop_tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            lhs = node.targets[0]
            if isinstance(lhs, ast.Name) and lhs.id == TARGET and isinstance(node.value, ast.Name):
                rebinds.append((node.lineno, node.value.id))
            if (
                isinstance(lhs, ast.Attribute)
                and isinstance(lhs.value, ast.Name)
                and lhs.value.id == 'App'
                and lhs.attr == '_build_collectors_tab'
                and isinstance(node.value, ast.Name)
            ):
                runtime.append((node.lineno, node.value.id))
    rebinds.sort()
    runtime.sort()
    assert rebinds == [(rebinds[0][0], '_wave44_spina_v27_build_collectors_tab')]
    assert runtime == [(runtime[0][0], TARGET)], runtime

    assert 'import tkinter as tk' in module_text
    assert 'from tkinter import messagebox, ttk' in module_text
    print('Wave 44 collector-tab presentation regression passed.')


if __name__ == '__main__':
    main()
