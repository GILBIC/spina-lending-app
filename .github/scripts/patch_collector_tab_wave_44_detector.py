from __future__ import annotations

import ast
import hashlib
from pathlib import Path

DESKTOP = Path('OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py')
TARGET = '_spina_v27_build_collectors_tab'
EXPECTED_LINES = 293
EXPECTED_SHA256 = '5ce718e8f43404331b044d2f3f43b81dc34b0782a15d45a317121e61da6701cb'


desktop_text = DESKTOP.read_text(encoding='utf-8')
lines = desktop_text.splitlines()
tree = ast.parse(desktop_text)
matches = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == TARGET]
if len(matches) != 1:
    raise SystemExit(f'Expected one {TARGET}, found {len(matches)}')
fn = matches[0]
source = '\n'.join(lines[fn.lineno - 1:fn.end_lineno])
line_count = len(source.splitlines())
inspection_hash = hashlib.sha256((source.strip() + '\n').encode()).hexdigest()
print(f'TARGET source lines={line_count} hash={inspection_hash}')
if line_count != EXPECTED_LINES or inspection_hash != EXPECTED_SHA256:
    raise SystemExit('Target source guard failed')

print('COLLECTOR TAB BINDING PROBE')
for node in ast.walk(tree):
    if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
        rendered = ast.unparse(node)
        if '_build_collectors_tab' in rendered or TARGET in rendered:
            print(f'line {getattr(node, "lineno", 0)}: {rendered}')
    elif isinstance(node, ast.Call):
        rendered = ast.unparse(node)
        if ('setattr' in rendered or 'configure' in rendered) and ('_build_collectors_tab' in rendered or TARGET in rendered):
            print(f'line {getattr(node, "lineno", 0)} call: {rendered}')
for node in tree.body:
    if isinstance(node, ast.ImportFrom):
        rendered = ast.unparse(node)
        if 'collector' in rendered.lower() and ('tab' in rendered.lower() or TARGET in rendered):
            print(f'line {node.lineno} import: {rendered}')
raise SystemExit('Wave 44 binding probe complete')
