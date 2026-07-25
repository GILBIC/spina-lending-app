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
inspection_normalized = source.strip() + '\n'
inspection_hash = hashlib.sha256(inspection_normalized.encode()).hexdigest()
if line_count != EXPECTED_LINES:
    raise SystemExit(f'Wave 44 line count changed: {line_count}')
if inspection_hash != EXPECTED_SHA256:
    raise SystemExit(f'Wave 44 historical hash changed: {inspection_hash}')

path = EXTRACTOR
text = path.read_text(encoding='utf-8')
old_sql = "re.compile(r'\\b(?:INSERT|UPDATE|DELETE|REPLACE|ALTER|DROP|CREATE)\\b', re.I)"
new_sql = "re.compile(r'\\b(?:INSERT\\s+INTO|UPDATE\\s+\\w+\\s+SET|DELETE\\s+FROM|REPLACE\\s+INTO|ALTER\\s+TABLE|DROP\\s+TABLE|CREATE\\s+TABLE)\\b', re.I)"
if text.count(old_sql) != 2:
    raise SystemExit(f'Expected two SQL detector patterns, found {text.count(old_sql)}')
text = text.replace(old_sql, new_sql)
old_normalized = "return '\\n'.join(line.rstrip() for line in text.strip().splitlines())"
new_normalized = "return '\\n'.join(line.rstrip() for line in text.strip().splitlines()) + '\\n'"
if text.count(old_normalized) != 1:
    raise SystemExit(f'Expected one compact normalized function, found {text.count(old_normalized)}')
text = text.replace(old_normalized, new_normalized)
old_block = "lines = text.strip().splitlines()\n    return '\\n'.join(line.rstrip() for line in lines)"
new_block = "lines = text.strip().splitlines()\n    return '\\n'.join(line.rstrip() for line in lines) + '\\n'"
if text.count(old_block) != 1:
    raise SystemExit(f'Expected one expanded normalized function, found {text.count(old_block)}')
text = text.replace(old_block, new_block)
path.write_text(text, encoding='utf-8')
print(f'Wave 44 source verified: {line_count} lines, historical hash {inspection_hash}.')
