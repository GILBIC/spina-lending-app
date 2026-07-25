from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

DESKTOP = Path('OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py')
MODULE = Path('spina_app/collector_tab_presentation.py')
TEST = Path('tools/test_collector_tab_presentation_wave_44.py')
WORKFLOW = Path('.github/workflows/collector-tab-presentation-wave-44.yml')
TARGET = '_spina_v27_build_collectors_tab'
EXPECTED_LINES = 293
EXPECTED_SHA256 = '5ce718e8f43404331b044d2f3f43b81dc34b0782a15d45a317121e61da6701cb'
EXPECTED_SIGNATURE = 'self'
EXPECTED_NESTED = []

BANNED_CALL_SUFFIXES = {
    'execute', 'executemany', 'commit', 'rollback',
    'add_or_update_transaction', 'add_or_update_transaction_by_uid',
    'delete_transaction', 'delete_transactions_for_day',
    'renew_client', 'delete_client', 'archive_client',
    'set_databank_day_close', 'reopen_databank_day',
    'write', 'write_text', 'write_bytes', 'unlink', 'remove', 'rename', 'replace',
}
SQL_WRITE_RE = re.compile(r'\b(?:INSERT|UPDATE|DELETE|REPLACE|ALTER|DROP|CREATE)\b', re.I)


def normalized(text: str) -> str:
    lines = text.strip().splitlines()
    return '\n'.join(line.rstrip() for line in lines)


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f'{left}.{node.attr}' if left else node.attr
    return ''


def signature_text(fn: ast.FunctionDef) -> str:
    args = []
    pos = list(fn.args.posonlyargs) + list(fn.args.args)
    defaults = [None] * (len(pos) - len(fn.args.defaults)) + list(fn.args.defaults)
    for arg, default in zip(pos, defaults):
        if default is None:
            args.append(arg.arg)
        else:
            args.append(f'{arg.arg}={ast.unparse(default)}')
    if fn.args.vararg:
        args.append('*' + fn.args.vararg.arg)
    elif fn.args.kwonlyargs:
        args.append('*')
    for arg, default in zip(fn.args.kwonlyargs, fn.args.kw_defaults):
        if default is None:
            args.append(arg.arg)
        else:
            args.append(f'{arg.arg}={ast.unparse(default)}')
    if fn.args.kwarg:
        args.append('**' + fn.args.kwarg.arg)
    return ', '.join(args)


def top_function(tree: ast.Module, name: str) -> ast.FunctionDef:
    matches = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name]
    if len(matches) != 1:
        raise SystemExit(f'Expected exactly one top-level {name}, found {len(matches)}')
    return matches[0]


def calls_in(fn: ast.FunctionDef) -> list[str]:
    return sorted({dotted(n.func) for n in ast.walk(fn) if isinstance(n, ast.Call) and dotted(n.func)})


def nested_callbacks(fn: ast.FunctionDef) -> list[str]:
    return [n.name for n in fn.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def assert_safe(fn: ast.FunctionDef, source: str) -> None:
    for node in ast.walk(fn):
        if isinstance(node, ast.Attribute) and dotted(node).startswith('self.db'):
            raise SystemExit(f'{TARGET} directly accesses self.db')
        if isinstance(node, ast.Call):
            name = dotted(node.func)
            suffix = name.rsplit('.', 1)[-1]
            if suffix in BANNED_CALL_SUFFIXES:
                raise SystemExit(f'{TARGET} contains banned call: {name}')
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and SQL_WRITE_RE.search(node.value):
            raise SystemExit(f'{TARGET} contains SQL mutation text')
    protected = ('principal', 'interest_rate', 'balance', 'advance_payment', 'day_close')
    lowered = source.lower()
    for token in protected:
        if f'self.db.{token}' in lowered:
            raise SystemExit(f'{TARGET} contains protected persistence token: {token}')


def assignment_targets(tree: ast.Module) -> list[tuple[int, str]]:
    found = []
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        lhs = node.targets[0]
        if (
            isinstance(lhs, ast.Attribute)
            and isinstance(lhs.value, ast.Name)
            and lhs.value.id == 'App'
            and lhs.attr == '_build_collectors_tab'
            and isinstance(node.value, ast.Name)
        ):
            found.append((node.lineno, node.value.id))
    return found


def build_module(source: str, calls: list[str]) -> str:
    return f'''"""Active collector-tab presentation extracted in Wave 44."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

_COLLECTOR_TAB_DEPENDENCIES = {{}}
_PROTECTED_GLOBALS = {{
    '__builtins__', '__cached__', '__doc__', '__file__', '__loader__',
    '__name__', '__package__', '__spec__',
    '_COLLECTOR_TAB_DEPENDENCIES', '_PROTECTED_GLOBALS',
    'configure_collector_tab_dependencies',
    'COLLECTOR_TAB_TARGET', 'COLLECTOR_TAB_SOURCE_LINES',
    'COLLECTOR_TAB_SOURCE_SHA256', 'COLLECTOR_TAB_SIGNATURE',
    'COLLECTOR_TAB_NESTED_CALLBACKS', 'COLLECTOR_TAB_CALLS',
    'tk', 'messagebox', 'ttk',
}}


def configure_collector_tab_dependencies(namespace):
    _COLLECTOR_TAB_DEPENDENCIES.clear()
    _COLLECTOR_TAB_DEPENDENCIES.update(namespace)
    for name, value in namespace.items():
        if name not in _PROTECTED_GLOBALS:
            globals()[name] = value


COLLECTOR_TAB_TARGET = {TARGET!r}
COLLECTOR_TAB_SOURCE_LINES = {EXPECTED_LINES}
COLLECTOR_TAB_SOURCE_SHA256 = {EXPECTED_SHA256!r}
COLLECTOR_TAB_SIGNATURE = {EXPECTED_SIGNATURE!r}
COLLECTOR_TAB_NESTED_CALLBACKS = {EXPECTED_NESTED!r}
COLLECTOR_TAB_CALLS = {calls!r}

{source.rstrip()}
'''


def build_test() -> str:
    return r'''from __future__ import annotations

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
SQL_WRITE_RE = re.compile(r'\b(?:INSERT|UPDATE|DELETE|REPLACE|ALTER|DROP|CREATE)\b', re.I)


def normalized(text: str) -> str:
    return '\n'.join(line.rstrip() for line in text.strip().splitlines())


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
    assert module.COLLECTOR_TAB_NESTED_CALLBACKS == []

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
    assert [n.name for n in fn.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))] == []

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
    assert len(top_functions(desktop_tree, '_spina_v25_build_collectors_tab')) == 1
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
    for node in desktop_tree.body:
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
    assert rebinds == [(rebinds[0][0], '_wave44_spina_v27_build_collectors_tab')]
    assert runtime
    assert runtime[-1][1] == TARGET, runtime

    assert 'import tkinter as tk' in module_text
    assert 'from tkinter import messagebox, ttk' in module_text
    print('Wave 44 collector-tab presentation regression passed.')


if __name__ == '__main__':
    main()
'''


def build_workflow() -> str:
    return '''name: Collector tab presentation Wave 44
on: [pull_request]
permissions:
  contents: read
concurrency:
  group: collector-tab-presentation-wave-44-${{ github.event.pull_request.number }}
  cancel-in-progress: true
jobs:
  validate:
    if: github.head_ref == 'agent/collector-tab-presentation-wave-44'
    runs-on: [self-hosted, Windows, X64]
    timeout-minutes: 45
    steps:
      - name: Check out exact PR head
        uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}
          fetch-depth: 0
      - name: Compile application, module, and test
        shell: cmd
        run: |
          python -m py_compile OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py
          python -m py_compile spina_app/collector_tab_presentation.py
          python -m py_compile tools/test_collector_tab_presentation_wave_44.py
          python -m compileall -q spina_app
      - name: Run exact collector-tab regression
        shell: cmd
        run: python tools/test_collector_tab_presentation_wave_44.py
      - name: Validate permanent architecture map
        uses: ./.github/actions/architecture-map-check
      - name: Run repository audits
        shell: cmd
        run: |
          if not exist artifacts mkdir artifacts
          python tools/redundancy_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json artifacts/wave-44-redundancy.json
          python tools/spina_quality_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json artifacts/wave-44-quality.json
      - name: Upload Wave 44 reports
        uses: actions/upload-artifact@v4
        with:
          name: collector-tab-presentation-wave-44-reports
          path: |
            artifacts/wave-44-redundancy.json
            artifacts/wave-44-quality.json
            architecture-map.json
            docs/architecture
          if-no-files-found: error
'''


def main() -> None:
    desktop_text = DESKTOP.read_text(encoding='utf-8')
    desktop_lines = desktop_text.splitlines()
    tree = ast.parse(desktop_text)
    fn = top_function(tree, TARGET)
    source = '\n'.join(desktop_lines[fn.lineno - 1:fn.end_lineno])
    source_norm = normalized(source)
    line_count = len(source.splitlines())
    digest = hashlib.sha256(source_norm.encode()).hexdigest()
    sig = signature_text(fn)
    nested = nested_callbacks(fn)
    calls = calls_in(fn)

    if line_count != EXPECTED_LINES:
        raise SystemExit(f'{TARGET} line count changed: {line_count} != {EXPECTED_LINES}')
    if digest != EXPECTED_SHA256:
        raise SystemExit(f'{TARGET} hash changed: {digest} != {EXPECTED_SHA256}')
    if sig != EXPECTED_SIGNATURE:
        raise SystemExit(f'{TARGET} signature changed: {sig!r}')
    if nested != EXPECTED_NESTED:
        raise SystemExit(f'{TARGET} nested callbacks changed: {nested!r}')
    assert_safe(fn, source)

    bindings = assignment_targets(tree)
    if not bindings or bindings[-1][1] != TARGET:
        raise SystemExit(f'{TARGET} is not the final App._build_collectors_tab binding: {bindings!r}')
    top_function(tree, '_spina_v25_build_collectors_tab')
    top_function(tree, '_build_collectors_tab')

    import_block = '''# Wave 44: active collector-tab presentation shell.\nfrom spina_app.collector_tab_presentation import (\n    configure_collector_tab_dependencies as _configure_wave44_collector_tab,\n    _spina_v27_build_collectors_tab as _wave44_spina_v27_build_collectors_tab,\n)\n_configure_wave44_collector_tab(globals())\n_spina_v27_build_collectors_tab = _wave44_spina_v27_build_collectors_tab'''

    new_lines = desktop_lines[:fn.lineno - 1] + import_block.splitlines() + desktop_lines[fn.end_lineno:]
    DESKTOP.write_text('\n'.join(new_lines) + '\n', encoding='utf-8')
    MODULE.parent.mkdir(parents=True, exist_ok=True)
    MODULE.write_text(build_module(source, calls), encoding='utf-8')
    TEST.parent.mkdir(parents=True, exist_ok=True)
    TEST.write_text(build_test(), encoding='utf-8')
    WORKFLOW.parent.mkdir(parents=True, exist_ok=True)
    WORKFLOW.write_text(build_workflow(), encoding='utf-8')

    report = {
        'target': TARGET,
        'source_lines': line_count,
        'source_sha256': digest,
        'signature': sig,
        'nested_callbacks': nested,
        'calls': calls,
        'runtime_bindings': bindings,
    }
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
