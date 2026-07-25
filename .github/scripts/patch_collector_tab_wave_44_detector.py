from __future__ import annotations

import ast
import hashlib
from pathlib import Path

DESKTOP = Path('OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py')
EXTRACTOR = Path('.github/scripts/extract_collector_tab_presentation_wave_44.py')
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
if line_count != EXPECTED_LINES:
    raise SystemExit(f'Wave 44 line count changed: {line_count}')
if inspection_hash != EXPECTED_SHA256:
    raise SystemExit(f'Wave 44 historical hash changed: {inspection_hash}')

bindings = []
for node in ast.walk(tree):
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
        bindings.append((node.lineno, node.value.id))
bindings.sort()
if not bindings or bindings[-1][1] != TARGET:
    raise SystemExit(f'Wave 44 runtime binding changed: {bindings!r}')

path = EXTRACTOR
text = path.read_text(encoding='utf-8')
old_sql = "re.compile(r'\\b(?:INSERT|UPDATE|DELETE|REPLACE|ALTER|DROP|CREATE)\\b', re.I)"
new_sql = "re.compile(r'\\b(?:INSERT\\s+INTO|UPDATE\\s+\\w+\\s+SET|DELETE\\s+FROM|REPLACE\\s+INTO|ALTER\\s+TABLE|DROP\\s+TABLE|CREATE\\s+TABLE)\\b', re.I)"
if text.count(old_sql) != 2:
    raise SystemExit(f'Expected two SQL detector patterns, found {text.count(old_sql)}')
text = text.replace(old_sql, new_sql)

old_compact_normalized = "return '\\n'.join(line.rstrip() for line in text.strip().splitlines())"
new_compact_normalized = "return '\\n'.join(line.rstrip() for line in text.strip().splitlines()) + '\\n'"
if text.count(old_compact_normalized) != 1:
    raise SystemExit(f'Expected one compact normalized function, found {text.count(old_compact_normalized)}')
text = text.replace(old_compact_normalized, new_compact_normalized)
old_expanded_normalized = "lines = text.strip().splitlines()\n    return '\\n'.join(line.rstrip() for line in lines)"
new_expanded_normalized = "lines = text.strip().splitlines()\n    return '\\n'.join(line.rstrip() for line in lines) + '\\n'"
if text.count(old_expanded_normalized) != 1:
    raise SystemExit(f'Expected one expanded normalized function, found {text.count(old_expanded_normalized)}')
text = text.replace(old_expanded_normalized, new_expanded_normalized)

old_extractor_scan = "for node in tree.body:\n        if not isinstance(node, ast.Assign) or len(node.targets) != 1:"
new_extractor_scan = "for node in ast.walk(tree):\n        if not isinstance(node, ast.Assign) or len(node.targets) != 1:"
if text.count(old_extractor_scan) != 1:
    raise SystemExit(f'Expected one extractor binding scan, found {text.count(old_extractor_scan)}')
text = text.replace(old_extractor_scan, new_extractor_scan)
old_return = "            found.append((node.lineno, node.value.id))\n    return found"
new_return = "            found.append((node.lineno, node.value.id))\n    return sorted(found)"
if text.count(old_return) != 1:
    raise SystemExit(f'Expected one binding return block, found {text.count(old_return)}')
text = text.replace(old_return, new_return)

old_test_scan = "    for node in desktop_tree.body:\n        if isinstance(node, ast.Assign) and len(node.targets) == 1:"
new_test_scan = "    for node in ast.walk(desktop_tree):\n        if isinstance(node, ast.Assign) and len(node.targets) == 1:"
if text.count(old_test_scan) != 1:
    raise SystemExit(f'Expected one test binding scan, found {text.count(old_test_scan)}')
text = text.replace(old_test_scan, new_test_scan)
old_test_asserts = "    assert rebinds == [(rebinds[0][0], '_wave44_spina_v27_build_collectors_tab')]\n    assert runtime"
new_test_asserts = "    rebinds.sort()\n    runtime.sort()\n    assert rebinds == [(rebinds[0][0], '_wave44_spina_v27_build_collectors_tab')]\n    assert runtime"
if text.count(old_test_asserts) != 1:
    raise SystemExit(f'Expected one test assertion block, found {text.count(old_test_asserts)}')
text = text.replace(old_test_asserts, new_test_asserts)

path.write_text(text, encoding='utf-8')
print(f'Wave 44 source and bindings verified: {line_count} lines, {inspection_hash}, {bindings}.')
