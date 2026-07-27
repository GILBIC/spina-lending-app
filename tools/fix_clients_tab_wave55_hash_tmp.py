from pathlib import Path

path = Path("tools/extract_clients_tab_wave55_tmp.py")
text = path.read_text(encoding="utf-8")
old = '    digest = hashlib.sha256(source_text.encode("utf-8")).hexdigest()'
new = '    dedented = textwrap.dedent(source_text)\n    digest = hashlib.sha256(dedented.encode("utf-8")).hexdigest()'
if old not in text:
    raise SystemExit("Expected Wave 55 digest line not found")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
