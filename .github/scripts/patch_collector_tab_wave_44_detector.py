from pathlib import Path

path = Path('.github/scripts/extract_collector_tab_presentation_wave_44.py')
text = path.read_text(encoding='utf-8')
old = "re.compile(r'\\b(?:INSERT|UPDATE|DELETE|REPLACE|ALTER|DROP|CREATE)\\b', re.I)"
new = "re.compile(r'\\b(?:INSERT\\s+INTO|UPDATE\\s+\\w+\\s+SET|DELETE\\s+FROM|REPLACE\\s+INTO|ALTER\\s+TABLE|DROP\\s+TABLE|CREATE\\s+TABLE)\\b', re.I)"
count = text.count(old)
if count != 2:
    raise SystemExit(f'Expected two SQL detector patterns, found {count}')
path.write_text(text.replace(old, new), encoding='utf-8')
print('Wave 44 SQL detector narrowed to real statements.')
