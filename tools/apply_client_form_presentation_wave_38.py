from __future__ import annotations

import ast
import hashlib
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "client_form_presentation.py"
TEST = ROOT / "tools" / "test_client_form_presentation_wave_38.py"
BOOT = ROOT / ".github" / "workflows" / "client-form-presentation-wave-38-bootstrap.yml"
PERM = ROOT / ".github" / "workflows" / "client-form-presentation-wave-38.yml"
SELF = ROOT / "tools" / "apply_client_form_presentation_wave_38.py"

EXPECTED_BASE = "05cad206933c566482b6b7d9187220a95cb94382"
TARGET = "_app__client_form"
EXPECTED_LINES = 649
ALLOWED_INITIAL = {
    ".github/workflows/client-form-presentation-wave-38-bootstrap.yml",
    "tools/apply_client_form_presentation_wave_38.py",
}
FORBIDDEN_TEXT = (
    "INSERT INTO", "UPDATE ", "DELETE FROM", "CREATE TABLE", "ALTER TABLE",
    "DROP TABLE", "TRUNCATE ", "ON CONFLICT", ".COMMIT(", ".ROLLBACK(",
    "WRITE_TEXT(", "WRITE_BYTES(", ".UNLINK(", "SAVE_SETTINGS(",
    "_WRITE_JSON_ATOMIC(", "ADD_TRANSACTION(", "UPDATE_TRANSACTION(",
    "DELETE_TRANSACTION(", "SET_CLIENT_NOTE(", "ADD_CLIENT(", "UPDATE_CLIENT(",
    "DELETE_CLIENT(", "RENEW", "OFFSET", "ADVANCE", "PASS_COUNT",
)
FORBIDDEN_CALL_SUFFIXES = {
    "commit", "rollback", "write", "write_text", "write_bytes", "unlink",
    "mkdir", "makedirs", "rename", "copy", "copy2", "move", "rmdir", "touch",
    "add_client", "update_client", "delete_client", "add_transaction",
    "update_transaction", "delete_transaction", "set_client_note",
    "save_settings", "_write_json_atomic", "_spina_pg_write_json",
}


def run(*args: str) -> str:
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()


def normalized_source(source: str) -> str:
    return textwrap.dedent(source).strip() + "\n"


def source_hash(source: str) -> str:
    return hashlib.sha256(normalized_source(source).encode("utf-8")).hexdigest()


def call_chain(node: ast.AST) -> list[str]:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return list(reversed(parts))


def validate_presentation_only(node: ast.AST, source: str) -> None:
    upper = source.upper()
    for token in FORBIDDEN_TEXT:
        if token in upper:
            raise SystemExit(f"Forbidden persistence/business token in {TARGET}: {token}")

    for item in ast.walk(node):
        if isinstance(item, ast.Attribute):
            chain = call_chain(item)
            if len(chain) >= 2 and chain[:2] == ["self", "db"]:
                raise SystemExit(f"Database access is not allowed in {TARGET}: {'.'.join(chain)}")
        if not isinstance(item, ast.Call):
            continue
        chain = call_chain(item.func)
        if chain and chain[-1].lower() in FORBIDDEN_CALL_SUFFIXES:
            raise SystemExit(f"Forbidden mutating call in {TARGET}: {'.'.join(chain)}")
        if chain and chain[-1] == "open":
            mode = None
            if len(item.args) >= 2 and isinstance(item.args[1], ast.Constant):
                mode = item.args[1].value
            for kw in item.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                    mode = kw.value.value
            if mode and any(flag in str(mode) for flag in ("w", "a", "x", "+")):
                raise SystemExit(f"File-writing open() is not allowed in {TARGET}")


def main() -> None:
    current = run("git", "rev-parse", "HEAD")
    merge_base = run("git", "merge-base", "HEAD", "origin/main")
    if merge_base != EXPECTED_BASE:
        raise SystemExit(f"Unexpected main base: {merge_base}; expected {EXPECTED_BASE}")

    changed = {line.strip() for line in run("git", "diff", "--name-only", EXPECTED_BASE, "HEAD").splitlines() if line.strip()}
    if changed != ALLOWED_INITIAL:
        raise SystemExit(f"Unexpected initial branch files: {sorted(changed)}")

    text = DESKTOP.read_text(encoding="utf-8")
    tree = ast.parse(text)
    targets = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == TARGET]
    if len(targets) != 1:
        raise SystemExit(f"Expected exactly one top-level {TARGET}, found {len(targets)}")
    node = targets[0]
    lines = text.splitlines(keepends=True)
    raw_source = "".join(lines[node.lineno - 1: node.end_lineno])
    exact_source = normalized_source(raw_source)
    if node.end_lineno - node.lineno + 1 != EXPECTED_LINES:
        raise SystemExit(f"Unexpected {TARGET} line count: {node.end_lineno - node.lineno + 1}")
    validate_presentation_only(node, exact_source)
    digest = source_hash(exact_source)

    module_header = f'''"""Client add/edit form presentation extracted in Wave 38."""\nfrom __future__ import annotations\n\n_CLIENT_FORM_DEPENDENCIES = {{}}\n_PROTECTED_GLOBALS = {{\n    "__builtins__", "__cached__", "__doc__", "__file__", "__loader__",\n    "__name__", "__package__", "__spec__", "_CLIENT_FORM_DEPENDENCIES",\n    "_PROTECTED_GLOBALS", "configure_client_form_dependencies",\n    "CLIENT_FORM_SOURCE_SHA256", "CLIENT_FORM_TARGET",\n}}\n\n\ndef configure_client_form_dependencies(namespace):\n    _CLIENT_FORM_DEPENDENCIES.clear()\n    _CLIENT_FORM_DEPENDENCIES.update(namespace)\n    for name, value in namespace.items():\n        if name not in _PROTECTED_GLOBALS:\n            globals()[name] = value\n\n\nCLIENT_FORM_TARGET = {TARGET!r}\nCLIENT_FORM_SOURCE_SHA256 = {digest!r}\n\n'''
    MODULE.parent.mkdir(parents=True, exist_ok=True)
    MODULE.write_text(module_header + exact_source, encoding="utf-8")

    replacement = '''# Wave 38: client add/edit form presentation.\nfrom spina_app.client_form_presentation import (\n    configure_client_form_dependencies as _configure_wave38_client_form,\n    _app__client_form as _wave38_app__client_form,\n)\n_configure_wave38_client_form(globals())\n_app__client_form = _wave38_app__client_form\n'''
    new_lines = lines[: node.lineno - 1] + [replacement] + lines[node.end_lineno:]
    DESKTOP.write_text("".join(new_lines), encoding="utf-8")

    test_source = f'''from __future__ import annotations\n\nimport ast\nimport hashlib\nimport textwrap\nfrom pathlib import Path\n\nROOT = Path(__file__).resolve().parents[1]\nDESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"\nMODULE = ROOT / "spina_app" / "client_form_presentation.py"\nTARGET = {TARGET!r}\nEXPECTED_LINES = {EXPECTED_LINES}\nEXPECTED_SHA256 = {digest!r}\nFORBIDDEN_TEXT = {FORBIDDEN_TEXT!r}\nFORBIDDEN_CALL_SUFFIXES = {sorted(FORBIDDEN_CALL_SUFFIXES)!r}\n\n\ndef normalized(source):\n    return textwrap.dedent(source).strip() + "\\n"\n\n\ndef call_chain(node):\n    parts = []\n    while isinstance(node, ast.Attribute):\n        parts.append(node.attr)\n        node = node.value\n    if isinstance(node, ast.Name):\n        parts.append(node.id)\n    return list(reversed(parts))\n\n\ndef main():\n    module_text = MODULE.read_text(encoding="utf-8")\n    mtree = ast.parse(module_text)\n    funcs = [n for n in mtree.body if isinstance(n, ast.FunctionDef) and n.name == TARGET]\n    assert len(funcs) == 1, len(funcs)\n    node = funcs[0]\n    lines = module_text.splitlines(keepends=True)\n    source = "".join(lines[node.lineno - 1: node.end_lineno])\n    assert node.end_lineno - node.lineno + 1 == EXPECTED_LINES\n    assert hashlib.sha256(normalized(source).encode("utf-8")).hexdigest() == EXPECTED_SHA256\n    upper = source.upper()\n    for token in FORBIDDEN_TEXT:\n        assert token not in upper, token\n    for item in ast.walk(node):\n        if isinstance(item, ast.Attribute):\n            chain = call_chain(item)\n            assert not (len(chain) >= 2 and chain[:2] == ["self", "db"]), chain\n        if isinstance(item, ast.Call):\n            chain = call_chain(item.func)\n            assert not (chain and chain[-1].lower() in FORBIDDEN_CALL_SUFFIXES), chain\n\n    desktop_text = DESKTOP.read_text(encoding="utf-8")\n    dtree = ast.parse(desktop_text)\n    originals = [n for n in dtree.body if isinstance(n, ast.FunctionDef) and n.name == TARGET]\n    assert not originals\n    assert "_configure_wave38_client_form(globals())" in desktop_text\n    assert "_app__client_form = _wave38_app__client_form" in desktop_text\n    assert "def _app_add_client_dialog" in desktop_text\n    assert "def _app_on_client_edit" in desktop_text\n    print("Wave 38 client-form regression passed:", EXPECTED_LINES, EXPECTED_SHA256)\n\n\nif __name__ == "__main__":\n    main()\n'''
    TEST.write_text(test_source, encoding="utf-8")

    workflow = '''name: Client form presentation Wave 38\non: [pull_request]\npermissions:\n  contents: read\njobs:\n  validate:\n    if: github.head_ref == 'agent/client-form-presentation-wave-38'\n    runs-on: [self-hosted, Windows, X64]\n    timeout-minutes: 45\n    steps:\n      - name: Check out exact PR head\n        uses: actions/checkout@v4\n        with:\n          ref: ${{ github.event.pull_request.head.sha }}\n          fetch-depth: 0\n      - name: Compile application, module, and test\n        shell: cmd\n        run: |\n          python -m py_compile OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py\n          python -m py_compile spina_app/client_form_presentation.py\n          python -m py_compile tools/test_client_form_presentation_wave_38.py\n          python -m compileall -q spina_app\n      - name: Run exact client-form regression\n        shell: cmd\n        run: python tools/test_client_form_presentation_wave_38.py\n      - name: Validate permanent architecture map\n        uses: ./.github/actions/architecture-map-check\n      - name: Run repository audits\n        shell: cmd\n        run: |\n          if not exist artifacts mkdir artifacts\n          python tools/redundancy_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json artifacts/wave-38-redundancy.json\n          python tools/spina_quality_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json artifacts/wave-38-quality.json\n      - name: Upload Wave 38 reports\n        uses: actions/upload-artifact@v4\n        with:\n          name: client-form-presentation-wave-38-reports\n          path: |\n            artifacts/wave-38-redundancy.json\n            artifacts/wave-38-quality.json\n            architecture-map.json\n            docs/architecture\n          if-no-files-found: error\n'''
    PERM.write_text(workflow, encoding="utf-8")

    if BOOT.exists():
        BOOT.unlink()
    if SELF.exists():
        SELF.unlink()

    print(f"Extracted {TARGET}: {EXPECTED_LINES} lines, sha256={digest}, branch_head={current}")


if __name__ == "__main__":
    main()
