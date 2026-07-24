"""Regression checks for login palette Wave 25."""

from __future__ import annotations

import ast
import hashlib
import importlib
from pathlib import Path

SOURCE = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
THEME_MODULE = Path("spina_app/theme_palettes.py")
TARGET = '_spina_v32_login_colors'
TARGET_SHA256 = '872d8262904f2e08e33ebc174b8679ad80582ac027b8a02f34c5a23a9088da16'
PROTECTED = {'_spina_v32_login_button': '5026d5e31401e7dc276a79f2625d117d23133e5e0da643a459e609fd99ff1d59', '_spina_v32_selected_label_for_user': '8b775aa3feb95037083709047367c8fe06c485a1521906aada4fee97d0b8564c', '_spina_v32_prompt_login': 'e0535b50f1296c0db8ff5b1f1540464f28f9e674c3eeae7954894823b01e6735'}
MARKER = '\n# Login color palette extracted in Wave 25.\n\n'
ORIGINAL_THEME_SHA256 = 'e347a7dca060ab283a8205ee6e1d57ab68f13858e216c90f07b57ce9881dbb2e'


def source_for(lines: list[str], node: ast.AST) -> str:
    return "\n".join(lines[node.lineno - 1 : node.end_lineno])


def main() -> None:
    app_text = SOURCE.read_text(encoding="utf-8")
    app_lines = app_text.splitlines()
    app_tree = ast.parse(app_text, filename=str(SOURCE))
    app_nodes = {
        node.name: node
        for node in app_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert TARGET not in app_nodes, "Login palette definition still remains in desktop source"

    imported = False
    for node in app_tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "spina_app.theme_palettes":
            if TARGET in {alias.name for alias in node.names}:
                imported = True
                break
    assert imported, "Login palette import is missing from desktop source"

    for name, expected_hash in PROTECTED.items():
        node = app_nodes.get(name)
        assert node is not None, f"Protected login function missing: {name}"
        digest = hashlib.sha256(source_for(app_lines, node).encode("utf-8")).hexdigest()
        assert digest == expected_hash, f"Protected login function changed: {name} {digest}"

    theme_text = THEME_MODULE.read_text(encoding="utf-8")
    assert theme_text.count(MARKER) == 1, "Wave 25 marker missing or duplicated"
    base_text, _extracted_text = theme_text.split(MARKER, 1)
    base_sha = hashlib.sha256(base_text.encode("utf-8")).hexdigest()
    assert base_sha == ORIGINAL_THEME_SHA256, f"Pre-existing theme module changed: {base_sha}"

    theme_lines = theme_text.splitlines()
    theme_tree = ast.parse(theme_text, filename=str(THEME_MODULE))
    matches = [
        node
        for node in theme_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == TARGET
    ]
    assert len(matches) == 1, f"Expected one login palette definition, found {len(matches)}"
    digest = hashlib.sha256(source_for(theme_lines, matches[0]).encode("utf-8")).hexdigest()
    assert digest == TARGET_SHA256, f"Login palette source changed: {digest}"

    module = importlib.import_module("spina_app.theme_palettes")
    palette = getattr(module, TARGET)
    assert callable(palette)

    class Dummy:
        pass

    light_obj = Dummy()
    light_obj.ui_theme = "light"
    light = palette(light_obj)
    assert light["bg"] == "#f3f6fb"
    assert light["panel"] == "#ffffff"
    assert light["fg"] == "#111827"
    assert light["blue"] == "#2563eb"

    dark_obj = Dummy()
    dark_obj.ui_theme = "dark"
    dark = palette(dark_obj)
    assert dark["bg"] == "#0f1117"
    assert dark["panel"] == "#171a23"
    assert dark["fg"] == "#f8fafc"
    assert dark["blue"] == "#60a5fa"

    default_dark = palette()
    assert default_dark == dark
    assert set(light) == set(dark)
    print("Login palette Wave 25 regression passed.")


if __name__ == "__main__":
    main()
