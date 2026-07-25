from __future__ import annotations

import ast
import hashlib
from pathlib import Path

DESKTOP = Path('OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py')
EXTRACTOR = Path('.github/scripts/extract_collector_tab_presentation_wave_44.py')
TARGET = '_spina_v27_build_collectors_tab'
EXPECTED_LINES = 293
EXPECTED_RAW_SHA256 = '3494cf016d693790236be39cdaa3248c72b6828fc06b5a7df764c452a385d68e'
EXPECTED_AST_SHA256 = '5ce718e8f43404331b044d2f3f43b81dc34b0782a15d45a317121e61da6701cb'


def normalized(text: str) -> str:
    return '\n'.join(line.rstrip() for line in text.strip().splitlines())


desktop_text = DESKTOP.read_text(encoding='utf-8')
lines = desktop_text.splitlines()
tree = ast.parse(desktop_text)
matches = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == TARGET]
if len(matches) != 1:
    raise SystemExit(f'Expected one {TARGET}, found {len(matches)}')
fn = matches[0]
source = '\n'.join(lines[fn.lineno - 1:fn.end_lineno])
line_count = len(source.splitlines())
raw_hash = hashlib.sha256(normalized(source).encode()).hexdigest()
ast_hash = hashlib.sha256(ast.unparse(fn).encode()).hexdigest()
if line_count != EXPECTED_LINES:
    raise SystemExit(f'Wave 44 line count changed: {line_count}')
if raw_hash != EXPECTED_RAW_SHA256:
    raise SystemExit(f'Wave 44 raw hash changed: {raw_hash}')
if ast_hash != EXPECTED_AST_SHA256:
    raise SystemExit(f'Wave 44 AST hash changed: {ast_hash}')

path = EXTRACTOR
text = path.read_text(encoding='utf-8')
old_sql = "re.compile(r'\\b(?:INSERT|UPDATE|DELETE|REPLACE|ALTER|DROP|CREATE)\\b', re.I)"
new_sql = "re.compile(r'\\b(?:INSERT\\s+INTO|UPDATE\\s+\\w+\\s+SET|DELETE\\s+FROM|REPLACE\\s+INTO|ALTER\\s+TABLE|DROP\\s+TABLE|CREATE\\s+TABLE)\\b', re.I)"
if text.count(old_sql) != 2:
    raise SystemExit(f'Expected two SQL detector patterns, found {text.count(old_sql)}')
text = text.replace(old_sql, new_sql)
if text.count(EXPECTED_AST_SHA256) != 2:
    raise SystemExit(f'Expected two prior hash literals, found {text.count(EXPECTED_AST_SHA256)}')
text = text.replace(EXPECTED_AST_SHA256, EXPECTED_RAW_SHA256)
path.write_text(text, encoding='utf-8')
print(f'Wave 44 source verified: {line_count} lines, raw {raw_hash}, AST {ast_hash}.')
