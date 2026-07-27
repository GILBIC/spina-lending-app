from pathlib import Path

path = Path(__file__).with_name("extract_system_data_wave56_tmp.py")
text = path.read_text(encoding="utf-8")
old = '''    text = raw.decode("utf-8-sig")
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text, filename=str(APP))
'''
new = '''    original_text = raw.decode("utf-8-sig")
    newline = "\\r\\n" if "\\r\\n" in original_text else "\\n"
    text = original_text.replace("\\r\\n", "\\n")
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text, filename=str(APP))
'''
if old not in text:
    raise SystemExit("Wave 56 newline source block not found")
text = text.replace(old, new, 1)
old = '''    encoded = new_text.encode("utf-8")
    if had_bom:
        encoded = codecs.BOM_UTF8 + encoded
'''
new = '''    if newline == "\\r\\n":
        new_text = new_text.replace("\\n", "\\r\\n")
    encoded = new_text.encode("utf-8")
    if had_bom:
        encoded = codecs.BOM_UTF8 + encoded
'''
if old not in text:
    raise SystemExit("Wave 56 newline output block not found")
text = text.replace(old, new, 1)
old_exact = r'    lowered = "\n".join(module.SYSTEM_DATA_PRESENTATION_CALLS).lower()'
new_exact = r'    lowered = "\\n".join(module.SYSTEM_DATA_PRESENTATION_CALLS).lower()'
if old_exact not in text:
    raise SystemExit("Wave 56 generated newline escape block not found")
text = text.replace(old_exact, new_exact, 1)
path.write_text(text, encoding="utf-8")
print("Wave 56 extractor newline normalization and generated escape fixed")
