from pathlib import Path

PATH = Path("tools/apply_clients_feature_wave_19.py")
text = PATH.read_text(encoding="utf-8")

replacements = [
    (
        'DEPENDENCIES = (\n    "_app__norm_lt_value",',
        'DEPENDENCIES = (\n    "_spina_v23_clients_colors",\n    "_app__norm_lt_value",',
    ),
    (
        'from spina_app.theme_palettes import _spina_v23_clients_colors\nfrom spina_app.ui_controls import _spina_v23_style_clients_tree',
        'from spina_app.ui_controls import _spina_v23_style_clients_tree',
    ),
    (
        '_REQUIRED_DEPENDENCIES = (\n    "_app__norm_lt_value",',
        '_REQUIRED_DEPENDENCIES = (\n    "_spina_v23_clients_colors",\n    "_app__norm_lt_value",',
    ),
    (
        '    assert set(missing) == {\n        "_app__norm_lt_value",',
        '    assert set(missing) == {\n        "_spina_v23_clients_colors",\n        "_app__norm_lt_value",',
    ),
    (
        '        {\n            "_app__norm_lt_value": lambda app, value: str(value or "Regular"),',
        '        {\n            "_spina_v23_clients_colors": lambda app=None: {},\n            "_app__norm_lt_value": lambda app, value: str(value or "Regular"),',
    ),
]

for old, new in replacements:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one occurrence of {old!r}, found {count}")
    text = text.replace(old, new, 1)

required = [
    '"_spina_v23_clients_colors",',
    'from spina_app.ui_controls import _spina_v23_style_clients_tree',
    '"_spina_v23_clients_colors": lambda app=None: {},',
]
for marker in required:
    if marker not in text:
        raise RuntimeError(f"Missing corrected marker: {marker}")

if 'from spina_app.theme_palettes import _spina_v23_clients_colors' in text:
    raise RuntimeError("Invalid Clients palette import still present")

PATH.write_text(text, encoding="utf-8")
print("Clients palette dependency bridge corrected")
