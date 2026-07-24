"""Apply SPINA modularization Wave 25 for the login color palette."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

SOURCE = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
THEME_MODULE = Path("spina_app/theme_palettes.py")
TEST = Path("tools/test_login_palette_wave_25.py")
PERMANENT_WORKFLOW = Path(".github/workflows/login-palette-wave-25.yml")
TEMP_WORKFLOW = Path(".github/workflows/apply-login-palette-wave-25.yml")
SELF = Path("tools/apply_login_palette_wave_25.py")

TARGET = "_spina_v32_login_colors"
TARGET_SHA256 = "872d8262904f2e08e33ebc174b8679ad80582ac027b8a02f34c5a23a9088da16"
EXPECTED_SOURCE_SHA256 = "147d70f752bea32b169bc72b5a4b7c443e475540a56960167a118ac9153102ff"
EXPECTED_THEME_SHA256 = "26eeb2b66506af81cc39a5fc3265b93f21938315336ed7e4c5cae34f2a5d7d6e"
PROTECTED = {
    "_spina_v32_login_button": "5026d5e31401e7dc276a79f2625d117d23133e5e0da643a459e609fd99ff1d59",
    "_spina_v32_selected_label_for_user": "8b775aa3feb95037083709047367c8fe06c485a1521906aada4fee97d0b8564c",
    "_spina_v32_prompt_login": "e0535b50f1296c0db8ff5b1f1540464f28f9e674c3eeae7954894823b01e6735",
}
MARKER = "\n# Login color palette extracted in Wave 25.\n\n"
IMPORT_LINE = "from spina_app.theme_palettes import _spina_v32_login_colors"


def function_source(lines: list[str], node: ast.AST) -> str:
    return "\n".join(lines[node.lineno - 1 : node.end_lineno])


def top_level_nodes(text: str, filename: str) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    tree = ast.parse(text, filename=filename)
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def function_hashes(text: str, filename: str) -> dict[str, str]:
    lines = text.splitlines()
    return {
        name: hashlib.sha256(function_source(lines, node).encode("utf-8")).hexdigest()
        for name, node in top_level_nodes(text, filename).items()
    }


def build_test_content(original_theme_sha256: str) -> str:
    return f'''"""Regression checks for login palette Wave 25."""

from __future__ import annotations

import ast
import hashlib
import importlib
from pathlib import Path

SOURCE = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
THEME_MODULE = Path("spina_app/theme_palettes.py")
TARGET = {TARGET!r}
TARGET_SHA256 = {TARGET_SHA256!r}
PROTECTED = {PROTECTED!r}
MARKER = {MARKER!r}
ORIGINAL_THEME_SHA256 = {original_theme_sha256!r}


def source_for(lines: list[str], node: ast.AST) -> str:
    return "\\n".join(lines[node.lineno - 1 : node.end_lineno])


def main() -> None:
    app_text = SOURCE.read_text(encoding="utf-8")
    app_lines = app_text.splitlines()
    app_tree = ast.parse(app_text, filename=str(SOURCE))
    app_nodes = {{
        node.name: node
        for node in app_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }}

    assert TARGET not in app_nodes, "Login palette definition still remains in desktop source"

    imported = False
    for node in app_tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "spina_app.theme_palettes":
            if TARGET in {{alias.name for alias in node.names}}:
                imported = True
                break
    assert imported, "Login palette import is missing from desktop source"

    for name, expected_hash in PROTECTED.items():
        node = app_nodes.get(name)
        assert node is not None, f"Protected login function missing: {{name}}"
        digest = hashlib.sha256(source_for(app_lines, node).encode("utf-8")).hexdigest()
        assert digest == expected_hash, f"Protected login function changed: {{name}} {{digest}}"

    theme_text = THEME_MODULE.read_text(encoding="utf-8")
    assert theme_text.count(MARKER) == 1, "Wave 25 marker missing or duplicated"
    base_text, _extracted_text = theme_text.split(MARKER, 1)
    base_sha = hashlib.sha256(base_text.encode("utf-8")).hexdigest()
    assert base_sha == ORIGINAL_THEME_SHA256, f"Pre-existing theme module changed: {{base_sha}}"

    theme_lines = theme_text.splitlines()
    theme_tree = ast.parse(theme_text, filename=str(THEME_MODULE))
    matches = [
        node
        for node in theme_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == TARGET
    ]
    assert len(matches) == 1, f"Expected one login palette definition, found {{len(matches)}}"
    digest = hashlib.sha256(source_for(theme_lines, matches[0]).encode("utf-8")).hexdigest()
    assert digest == TARGET_SHA256, f"Login palette source changed: {{digest}}"

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
'''


PERMANENT_WORKFLOW_CONTENT = r'''name: Login palette Wave 25

on:
  pull_request:

permissions:
  contents: read

jobs:
  validate:
    if: github.head_ref == 'agent/login-palette-wave-25'
    runs-on: [self-hosted, Windows, X64]
    timeout-minutes: 30
    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Verify local Python
        shell: cmd
        run: |
          where python
          python --version

      - name: Compile application, theme module, and test
        shell: cmd
        run: |
          python -m py_compile OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py
          python -m py_compile spina_app\theme_palettes.py
          python -m py_compile tools\test_login_palette_wave_25.py

      - name: Run login palette regression
        shell: cmd
        run: python -m tools.test_login_palette_wave_25

      - name: Run redundancy audit
        shell: cmd
        run: python tools\redundancy_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json redundancy-report.json

      - name: Run SPINA quality audit
        shell: cmd
        run: python tools\spina_quality_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json quality-report.json

      - name: Upload audit reports
        uses: actions/upload-artifact@v4
        with:
          name: login-palette-wave-25-audits
          path: |
            redundancy-report.json
            quality-report.json
'''


def main() -> None:
    source_text = SOURCE.read_text(encoding="utf-8")
    source_sha = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    if source_sha != EXPECTED_SOURCE_SHA256:
        raise SystemExit(f"Unexpected current-main source SHA: {source_sha}")

    theme_base_text = THEME_MODULE.read_text(encoding="utf-8")
    theme_sha = hashlib.sha256(theme_base_text.encode("utf-8")).hexdigest()
    if theme_sha != EXPECTED_THEME_SHA256:
        raise SystemExit(f"Unexpected theme module SHA: {theme_sha}")
    if MARKER in theme_base_text:
        raise SystemExit("Wave 25 marker already exists in theme module")

    source_lines = source_text.splitlines()
    source_nodes = top_level_nodes(source_text, str(SOURCE))
    target_node = source_nodes.get(TARGET)
    if target_node is None:
        raise SystemExit(f"Missing target function: {TARGET}")

    target_source = function_source(source_lines, target_node)
    target_digest = hashlib.sha256(target_source.encode("utf-8")).hexdigest()
    if target_digest != TARGET_SHA256:
        raise SystemExit(f"Target source hash mismatch: {target_digest}")

    for name, expected_hash in PROTECTED.items():
        node = source_nodes.get(name)
        if node is None:
            raise SystemExit(f"Missing protected login function: {name}")
        digest = hashlib.sha256(function_source(source_lines, node).encode("utf-8")).hexdigest()
        if digest != expected_hash:
            raise SystemExit(f"Protected login source changed for {name}: {digest}")

    before_hashes = function_hashes(source_text, str(SOURCE))
    start, end = target_node.lineno, target_node.end_lineno
    output = source_lines[: start - 1] + [IMPORT_LINE, ""] + source_lines[end:]
    new_source_text = "\n".join(output) + "\n"

    after_hashes = function_hashes(new_source_text, str(SOURCE))
    expected_names = set(before_hashes) - {TARGET}
    if set(after_hashes) != expected_names:
        missing = sorted(expected_names - set(after_hashes))
        extra = sorted(set(after_hashes) - expected_names)
        raise SystemExit(f"Non-target function set changed; missing={missing}, extra={extra}")
    for name in expected_names:
        if before_hashes[name] != after_hashes[name]:
            raise SystemExit(f"Non-target function changed: {name}")

    original_theme_sha256 = hashlib.sha256(theme_base_text.encode("utf-8")).hexdigest()
    SOURCE.write_text(new_source_text, encoding="utf-8")
    THEME_MODULE.write_text(theme_base_text + MARKER + target_source + "\n", encoding="utf-8")
    TEST.write_text(build_test_content(original_theme_sha256), encoding="utf-8")
    PERMANENT_WORKFLOW.write_text(PERMANENT_WORKFLOW_CONTENT, encoding="utf-8")

    TEMP_WORKFLOW.unlink(missing_ok=True)
    SELF.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
