from __future__ import annotations

import argparse
import ast
import hashlib
import importlib
import re
from pathlib import Path

DESKTOP = Path('OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py')
MODULE_PATH = Path('spina_app/collector_tab_presentation.py')
TARGET = '_spina_v27_build_collectors_tab'
EXPECTED_LINES = 293
EXPECTED_SHA256 = '5ce718e8f43404331b044d2f3f43b81dc34b0782a15d45a317121e61da6701cb'
EXPECTED_SIGNATURE = 'self'
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


def module_data():
    module = importlib.import_module('spina_app.collector_tab_presentation')
    text = MODULE_PATH.read_text(encoding='utf-8')
    lines = text.splitlines()
    tree = ast.parse(text)
    defs = top_functions(tree, TARGET)
    if len(defs) != 1:
        raise AssertionError(f'module target count={len(defs)}')
    return module, text, lines, tree, defs[0]


def desktop_data():
    text = DESKTOP.read_text(encoding='utf-8')
    tree = ast.parse(text)
    return text, tree


def check_metadata():
    module, *_ = module_data()
    actual = (
        module.COLLECTOR_TAB_TARGET,
        module.COLLECTOR_TAB_SOURCE_LINES,
        module.COLLECTOR_TAB_SOURCE_SHA256,
        module.COLLECTOR_TAB_SIGNATURE,
        module.COLLECTOR_TAB_NESTED_CALLBACKS,
    )
    expected = (TARGET, EXPECTED_LINES, EXPECTED_SHA256, EXPECTED_SIGNATURE, [])
    if actual != expected:
        raise AssertionError(f'metadata actual={actual!r} expected={expected!r}')
    print('metadata checkpoint passed')


def check_module_source():
    module, _text, lines, _tree, fn = module_data()
    source = source_for(lines, fn)
    actual = {
        'lines': len(source.splitlines()),
        'hash': hashlib.sha256(normalized(source).encode()).hexdigest(),
        'signature': signature_text(fn),
        'nested': [n.name for n in fn.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))],
        'calls': sorted({dotted(n.func) for n in ast.walk(fn) if isinstance(n, ast.Call) and dotted(n.func)}),
    }
    expected = {
        'lines': EXPECTED_LINES,
        'hash': EXPECTED_SHA256,
        'signature': EXPECTED_SIGNATURE,
        'nested': [],
        'calls': module.COLLECTOR_TAB_CALLS,
    }
    if actual != expected:
        for key in expected:
            if actual[key] != expected[key]:
                raise AssertionError(f'module source mismatch {key}: actual={actual[key]!r} expected={expected[key]!r}')
    print('module-source checkpoint passed')


def check_safety():
    _module, _text, _lines, _tree, fn = module_data()
    for node in ast.walk(fn):
        if isinstance(node, ast.Attribute) and dotted(node).startswith('self.db'):
            raise AssertionError(f'direct database attribute: {dotted(node)}')
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and SQL_WRITE_RE.search(node.value):
            raise AssertionError(f'SQL-like mutation text: {node.value!r}')
    print('safety checkpoint passed')


def check_desktop_structure():
    _text, tree = desktop_data()
    values = {
        'target_defs': len(top_functions(tree, TARGET)),
        'v25_defs': len(top_functions(tree, '_spina_v25_build_collectors_tab')),
        'original_defs': len(top_functions(tree, '_build_collectors_tab')),
    }
    expected = {'target_defs': 0, 'v25_defs': 1, 'original_defs': 1}
    if values != expected:
        raise AssertionError(f'desktop structure actual={values!r} expected={expected!r}')
    print('desktop-structure checkpoint passed')


def check_imports():
    _text, tree = desktop_data()
    imports = [
        n for n in tree.body
        if isinstance(n, ast.ImportFrom)
        and n.module == 'spina_app.collector_tab_presentation'
    ]
    if len(imports) != 1:
        raise AssertionError(f'import count={len(imports)}')
    aliases = {(a.name, a.asname) for a in imports[0].names}
    expected = (TARGET, '_wave44_spina_v27_build_collectors_tab')
    if expected not in aliases:
        raise AssertionError(f'missing import alias {expected!r}; aliases={sorted(aliases)!r}')
    print('imports checkpoint passed')


def check_bindings():
    _text, tree = desktop_data()
    rebinds = []
    runtime = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
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
    if len(rebinds) != 1 or rebinds[0][1] != '_wave44_spina_v27_build_collectors_tab':
        raise AssertionError(f'rebinds={rebinds!r}')
    if not runtime or runtime[-1][1] != TARGET:
        raise AssertionError(f'runtime bindings={runtime!r}')
    print(f'bindings checkpoint passed: rebinds={rebinds!r}, runtime={runtime!r}')


CHECKS = {
    'metadata': check_metadata,
    'module-source': check_module_source,
    'safety': check_safety,
    'desktop-structure': check_desktop_structure,
    'imports': check_imports,
    'bindings': check_bindings,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('check', choices=CHECKS)
    args = parser.parse_args()
    CHECKS[args.check]()


if __name__ == '__main__':
    main()
