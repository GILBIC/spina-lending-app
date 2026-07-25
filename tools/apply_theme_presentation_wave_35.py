from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "theme_presentation.py"
TEST = ROOT / "tools" / "test_theme_presentation_wave_35.py"
BOOT = ROOT / ".github" / "workflows" / "theme-presentation-wave-35-bootstrap.yml"
PERM = ROOT / ".github" / "workflows" / "theme-presentation-wave-35.yml"

EXPECTED_BASE = "fbef746fe88c7f584e04345fa9bc1ffc2923ce9f"
TARGETS = (
    "_theme_toggle_text",
    "_theme_palette",
    "_apply_ui_theme",
    "_apply_tk_theme_recursive",
    "_refresh_modern_shell_theme",
    "_refresh_header_theme",
)
ALLOWED_INITIAL = {
    ".github/workflows/theme-presentation-wave-35-bootstrap.yml",
    "tools/apply_theme_presentation_wave_35.py",
}
FORBIDDEN_TEXT = (
    "SAVE_SETTINGS",
    "LOAD_SETTINGS",
    "_WRITE_JSON_ATOMIC",
    "INSERT INTO",
    "UPDATE ",
    "DELETE FROM",
    "CREATE TABLE",
    "ALTER TABLE",
    "DROP TABLE",
    ".COMMIT(",
    ".ROLLBACK(",
    "WRITE_TEXT(",
    "WRITE_BYTES(",
    ".UNLINK(",
)
MUTATING_CALLS = {
    "save_settings", "load_settings", "_write_json_atomic", "commit", "rollback",
    "write", "write_text", "write_bytes", "unlink", "remove", "rename", "mkdir",
    "makedirs", "rmdir", "touch", "copy", "copy2", "move",
}


def run(*args: str) -> str:
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def normalized_source(source: str) -> str:
    return textwrap.dedent(source).strip() + "\n"


def source_hash(source: str) -> str:
    return hashlib.sha256(normalized_source(source).encode("utf-8")).hexdigest()


def validate_presentation_only(name: str, node: ast.AST, source: str) -> None:
    upper = source.upper()
    for token in FORBIDDEN_TEXT:
        if token in upper:
            raise SystemExit(f"{name} contains forbidden persistence/write token: {token}")
    for item in ast.walk(node):
        if not isinstance(item, ast.Call):
            continue
        fn = item.func
        call_name = fn.attr if isinstance(fn, ast.Attribute) else fn.id if isinstance(fn, ast.Name) else ""
        if call_name.lower() in MUTATING_CALLS:
            raise SystemExit(f"{name} calls forbidden mutating helper: {call_name}")
        if call_name == "open":
            raise SystemExit(f"{name} opens a file")


def main() -> None:
    subprocess.run(["git", "fetch", "origin", "main", "--quiet"], cwd=ROOT, check=True)
    merge_base = run("git", "merge-base", "HEAD", "origin/main")
    if merge_base != EXPECTED_BASE:
        raise SystemExit(f"Unexpected main base: {merge_base}")

    changed = {
        line.strip()
        for line in run("git", "diff", "--name-only", f"{EXPECTED_BASE}..HEAD").splitlines()
        if line.strip()
    }
    unexpected = changed - ALLOWED_INITIAL
    if unexpected:
        raise SystemExit(f"Unexpected initial files: {sorted(unexpected)}")

    desktop_text = DESKTOP.read_text(encoding="utf-8-sig")
    tree = ast.parse(desktop_text, filename=str(DESKTOP))
    app_class = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "App"
    )
    methods = {
        node.name: node
        for node in app_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in TARGETS
    }
    missing = [name for name in TARGETS if name not in methods]
    if missing:
        raise SystemExit(f"Missing App theme methods: {missing}")

    sources: dict[str, str] = {}
    hashes: dict[str, str] = {}
    total_lines = 0
    for name in TARGETS:
        node = methods[name]
        segment = ast.get_source_segment(desktop_text, node)
        if not segment:
            raise SystemExit(f"Could not read source for {name}")
        validate_presentation_only(name, node, segment)
        sources[name] = normalized_source(segment)
        hashes[name] = source_hash(segment)
        total_lines += (node.end_lineno or node.lineno) - node.lineno + 1

    if not 290 <= total_lines <= 340:
        raise SystemExit(f"Unexpected Wave 35 theme volume: {total_lines} lines")

    header = (
        '"""High-volume theme presentation helpers extracted in Wave 35."""\n'
        "from __future__ import annotations\n\n"
        "_THEME_PRESENTATION_DEPENDENCIES = {}\n"
        "_PROTECTED_GLOBALS = {\n"
        '    "__builtins__", "__cached__", "__doc__", "__file__", "__loader__",\n'
        '    "__name__", "__package__", "__spec__", "_THEME_PRESENTATION_DEPENDENCIES",\n'
        '    "_PROTECTED_GLOBALS", "configure_theme_presentation_dependencies",\n'
        '    "THEME_PRESENTATION_SOURCE_SHA256", "THEME_PRESENTATION_TARGETS",\n'
        "}\n\n\n"
        "def configure_theme_presentation_dependencies(namespace):\n"
        "    _THEME_PRESENTATION_DEPENDENCIES.clear()\n"
        "    _THEME_PRESENTATION_DEPENDENCIES.update(namespace)\n"
        "    for name, value in namespace.items():\n"
        "        if name not in _PROTECTED_GLOBALS:\n"
        "            globals()[name] = value\n\n\n"
    )
    module_text = (
        header
        + "THEME_PRESENTATION_TARGETS = " + repr(TARGETS) + "\n"
        + "THEME_PRESENTATION_SOURCE_SHA256 = " + json.dumps(hashes, indent=4, sort_keys=True) + "\n\n"
        + "\n\n".join(sources[name].rstrip() for name in TARGETS)
        + "\n"
    )
    MODULE.write_text(module_text, encoding="utf-8")

    import_lines = ",\n    ".join(f"{name} as _theme_wave35_{name}" for name in TARGETS)
    assignments = "\n".join(f"App.{name} = _theme_wave35_{name}" for name in TARGETS)
    wiring = f"""# Wave 35: high-volume theme presentation methods.
from spina_app.theme_presentation import (
    configure_theme_presentation_dependencies as _configure_theme_wave35_dependencies,
    {import_lines},
)
_configure_theme_wave35_dependencies(globals())
{assignments}

"""

    lines = desktop_text.splitlines(keepends=True)
    spans = {node.lineno: (node.end_lineno or node.lineno) for node in methods.values()}
    class_end = app_class.end_lineno or app_class.lineno
    output: list[str] = []
    line_no = 1
    inserted = False
    while line_no <= len(lines):
        if line_no in spans:
            output.append("\n")
            line_no = spans[line_no] + 1
            continue
        if line_no == class_end + 1 and not inserted:
            output.append(wiring)
            inserted = True
        output.append(lines[line_no - 1])
        line_no += 1
    if not inserted:
        output.append(wiring)

    rewritten = "".join(output)
    ast.parse(rewritten, filename=str(DESKTOP))
    DESKTOP.write_text(rewritten, encoding="utf-8")

    test_text = f'''from __future__ import annotations

import ast
import hashlib
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "theme_presentation.py"
TARGETS = {TARGETS!r}
EXPECTED = {hashes!r}
EXPECTED_TOTAL_LINES = {total_lines}
FORBIDDEN_TEXT = {FORBIDDEN_TEXT!r}
MUTATING_CALLS = {tuple(sorted(MUTATING_CALLS))!r}


def normalized(source: str) -> str:
    return textwrap.dedent(source).strip() + "\\n"


def digest(source: str) -> str:
    return hashlib.sha256(normalized(source).encode("utf-8")).hexdigest()


def main() -> None:
    module_text = MODULE.read_text(encoding="utf-8")
    module_tree = ast.parse(module_text, filename=str(MODULE))
    funcs = {{
        node.name: node
        for node in module_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }}
    assert set(TARGETS) <= set(funcs), sorted(set(TARGETS) - set(funcs))
    actual_lines = 0
    for name in TARGETS:
        node = funcs[name]
        segment = ast.get_source_segment(module_text, node)
        assert segment
        assert digest(segment) == EXPECTED[name], name
        actual_lines += (node.end_lineno or node.lineno) - node.lineno + 1
        upper = segment.upper()
        for token in FORBIDDEN_TEXT:
            assert token not in upper, (name, token)
        for item in ast.walk(node):
            if not isinstance(item, ast.Call):
                continue
            fn = item.func
            call_name = fn.attr if isinstance(fn, ast.Attribute) else fn.id if isinstance(fn, ast.Name) else ""
            assert call_name.lower() not in MUTATING_CALLS, (name, call_name)
            assert call_name != "open", name
    assert actual_lines == EXPECTED_TOTAL_LINES, (actual_lines, EXPECTED_TOTAL_LINES)

    desktop_text = DESKTOP.read_text(encoding="utf-8")
    desktop_tree = ast.parse(desktop_text, filename=str(DESKTOP))
    app_class = next(node for node in desktop_tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    remaining = {{
        node.name
        for node in app_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }}
    assert not (set(TARGETS) & remaining), sorted(set(TARGETS) & remaining)
    assigned = set()
    for node in desktop_tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "App":
            if target.attr in TARGETS:
                assigned.add(target.attr)
                assert node.lineno > (app_class.end_lineno or app_class.lineno)
    assert assigned == set(TARGETS), sorted(set(TARGETS) - assigned)
    assert "def set_theme(" in desktop_text
    assert "def toggle_theme(" in desktop_text
    print(f"Wave 35 theme presentation regression passed: {{len(TARGETS)}} methods / {{actual_lines}} lines.")


if __name__ == "__main__":
    main()
'''
    TEST.write_text(test_text, encoding="utf-8")

    permanent = """name: Theme presentation Wave 35
on: [pull_request]
permissions:
  contents: read
jobs:
  validate:
    if: github.head_ref == 'agent/theme-presentation-wave-35'
    runs-on: [self-hosted, Windows, X64]
    timeout-minutes: 40
    steps:
      - name: Check out exact PR head
        uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}
          fetch-depth: 0
      - name: Compile application, module, and test
        shell: cmd
        run: |
          python -m py_compile OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py
          python -m py_compile spina_app\theme_presentation.py
          python -m py_compile tools\test_theme_presentation_wave_35.py
          python -m compileall -q spina_app
      - name: Run high-volume theme regression
        shell: cmd
        run: python tools\test_theme_presentation_wave_35.py
      - name: Validate permanent architecture map
        uses: ./.github/actions/architecture-map-check
      - name: Run repository audits
        shell: cmd
        run: |
          if not exist artifacts mkdir artifacts
          python tools\redundancy_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json artifacts/wave-35-redundancy.json
          python tools\spina_quality_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json artifacts/wave-35-quality.json
      - name: Upload Wave 35 reports
        uses: actions/upload-artifact@v4
        with:
          name: theme-presentation-wave-35-reports
          path: |
            artifacts/wave-35-redundancy.json
            artifacts/wave-35-quality.json
            architecture-map.json
            docs/architecture
          if-no-files-found: error
"""
    PERM.write_text(permanent, encoding="utf-8")

    if BOOT.exists():
        BOOT.unlink()
    Path(__file__).unlink()
    print(f"Wave 35 extracted {len(TARGETS)} theme presentation methods ({total_lines} lines).")


if __name__ == "__main__":
    main()
