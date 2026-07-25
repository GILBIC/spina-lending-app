from __future__ import annotations

import ast
import hashlib
import re
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "login_dialog_presentation.py"
TEST = ROOT / "tools" / "test_login_dialog_presentation_wave_45.py"
WORKFLOW = ROOT / ".github" / "workflows" / "login-dialog-presentation-wave-45.yml"

TARGET = "_spina_v32_prompt_login"
EXPECTED_LINES = 234
EXPECTED_SHA256 = "0dc7c87e702bf93da77bbf6a9fc490a005114716e4ef487f10a203bfe75e48a3"
EXPECTED_SIGNATURE = "self, default_user: str='admin'"
EXPECTED_NESTED = ["_toggle_show", "_refresh_account_info", "_ok", "_cancel", "_enter"]
OLD_METHOD = "_prompt_login"
EXPECTED_OLD_LINES = 126
EXPECTED_OLD_SHA256 = "095ec5385a973531328c2dbc57c45fef867b2b422bd1713f3677dcc2bc30e75d"
SQL_WRITE_RE = re.compile(
    r"\b(?:INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|REPLACE\s+INTO|"
    r"ALTER\s+TABLE|DROP\s+TABLE|CREATE\s+TABLE|TRUNCATE\s+TABLE)\b",
    re.I,
)
FILESYSTEM_MUTATORS = {
    "write", "write_text", "write_bytes", "unlink", "remove", "rmtree",
    "rename", "replace", "mkdir", "makedirs", "dump", "dumps",
}


def normalized(text: str) -> str:
    return textwrap.dedent(text).strip() + "\n"


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def source_for(lines: list[str], node: ast.AST) -> str:
    return "".join(lines[node.lineno - 1 : node.end_lineno])


def signature_text(fn: ast.FunctionDef) -> str:
    return ast.unparse(fn.args)


def direct_nested(fn: ast.FunctionDef) -> list[str]:
    return [
        node.name for node in fn.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def calls_for(fn: ast.FunctionDef) -> list[str]:
    return sorted({
        dotted(node.func)
        for node in ast.walk(fn)
        if isinstance(node, ast.Call) and dotted(node.func)
    })


def find_top_function(tree: ast.Module, name: str) -> ast.FunctionDef:
    matches = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(matches) != 1:
        raise SystemExit(f"Expected one top-level {name}, found {len(matches)}")
    return matches[0]


def find_app_method(tree: ast.Module, name: str) -> ast.FunctionDef:
    app = next((node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "App"), None)
    if app is None:
        raise SystemExit("App class not found")
    matches = [node for node in app.body if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(matches) != 1:
        raise SystemExit(f"Expected one App.{name}, found {len(matches)}")
    return matches[0]


def runtime_bindings(tree: ast.Module, attr: str) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        lhs = node.targets[0]
        if (
            isinstance(lhs, ast.Attribute)
            and isinstance(lhs.value, ast.Name)
            and lhs.value.id == "App"
            and lhs.attr == attr
            and isinstance(node.value, ast.Name)
        ):
            found.append((node.lineno, node.value.id))
    return sorted(found)


def assert_safe(fn: ast.FunctionDef) -> None:
    for node in ast.walk(fn):
        if isinstance(node, ast.Attribute) and dotted(node).startswith("self.db"):
            raise SystemExit(f"Direct database access found: {dotted(node)}")
        if isinstance(node, ast.Call):
            name = dotted(node.func)
            if name.split(".")[-1].lower() in FILESYSTEM_MUTATORS:
                raise SystemExit(f"Filesystem mutation call found: {name}")
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if SQL_WRITE_RE.search(node.value):
                raise SystemExit(f"SQL write found in string: {node.value!r}")


def module_text(source: str, calls: list[str]) -> str:
    protected = [
        "__builtins__", "__cached__", "__doc__", "__file__", "__loader__",
        "__name__", "__package__", "__spec__", "_LOGIN_DIALOG_DEPENDENCIES",
        "_PROTECTED_GLOBALS", "configure_login_dialog_dependencies",
        "LOGIN_DIALOG_TARGET", "LOGIN_DIALOG_SOURCE_LINES",
        "LOGIN_DIALOG_SOURCE_SHA256", "LOGIN_DIALOG_SIGNATURE",
        "LOGIN_DIALOG_NESTED_CALLBACKS", "LOGIN_DIALOG_CALLS",
        "tk", "messagebox", "ttk",
    ]
    return (
        '"""Modern account login dialog presentation extracted in Wave 45."""\n'
        "from __future__ import annotations\n\n"
        "import tkinter as tk\n"
        "from tkinter import messagebox, ttk\n\n"
        "_LOGIN_DIALOG_DEPENDENCIES = {}\n"
        f"_PROTECTED_GLOBALS = {set(protected)!r}\n\n"
        "def configure_login_dialog_dependencies(namespace):\n"
        "    _LOGIN_DIALOG_DEPENDENCIES.clear()\n"
        "    _LOGIN_DIALOG_DEPENDENCIES.update(namespace)\n"
        "    for name, value in namespace.items():\n"
        "        if name not in _PROTECTED_GLOBALS:\n"
        "            globals()[name] = value\n\n"
        f"LOGIN_DIALOG_TARGET = {TARGET!r}\n"
        f"LOGIN_DIALOG_SOURCE_LINES = {EXPECTED_LINES}\n"
        f"LOGIN_DIALOG_SOURCE_SHA256 = {EXPECTED_SHA256!r}\n"
        f"LOGIN_DIALOG_SIGNATURE = {EXPECTED_SIGNATURE!r}\n"
        f"LOGIN_DIALOG_NESTED_CALLBACKS = {EXPECTED_NESTED!r}\n"
        f"LOGIN_DIALOG_CALLS = {calls!r}\n\n"
        + normalized(source)
    )


def test_text() -> str:
    return f'''from __future__ import annotations

import ast
import hashlib
import importlib
import re
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE_PATH = ROOT / "spina_app/login_dialog_presentation.py"
TARGET = {TARGET!r}
EXPECTED_LINES = {EXPECTED_LINES}
EXPECTED_SHA256 = {EXPECTED_SHA256!r}
EXPECTED_SIGNATURE = {EXPECTED_SIGNATURE!r}
EXPECTED_NESTED = {EXPECTED_NESTED!r}
EXPECTED_OLD_LINES = {EXPECTED_OLD_LINES}
EXPECTED_OLD_SHA256 = {EXPECTED_OLD_SHA256!r}
SQL_WRITE_RE = re.compile(r"\\b(?:INSERT\\s+INTO|UPDATE\\s+\\w+\\s+SET|DELETE\\s+FROM|REPLACE\\s+INTO|ALTER\\s+TABLE|DROP\\s+TABLE|CREATE\\s+TABLE|TRUNCATE\\s+TABLE)\\b", re.I)
FILESYSTEM_MUTATORS = {{"write", "write_text", "write_bytes", "unlink", "remove", "rmtree", "rename", "replace", "mkdir", "makedirs", "dump", "dumps"}}


def normalized(text: str) -> str:
    return textwrap.dedent(text).strip() + "\\n"


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{{left}}.{{node.attr}}" if left else node.attr
    return ""


def source_for(lines: list[str], node: ast.AST) -> str:
    return "".join(lines[node.lineno - 1:node.end_lineno])


def top_functions(tree: ast.Module, name: str):
    return [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name]


def app_method(tree: ast.Module, name: str) -> ast.FunctionDef:
    app = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    matches = [node for node in app.body if isinstance(node, ast.FunctionDef) and node.name == name]
    assert len(matches) == 1, len(matches)
    return matches[0]


def main() -> None:
    module = importlib.import_module("spina_app.login_dialog_presentation")
    assert module.LOGIN_DIALOG_TARGET == TARGET
    assert module.LOGIN_DIALOG_SOURCE_LINES == EXPECTED_LINES
    assert module.LOGIN_DIALOG_SOURCE_SHA256 == EXPECTED_SHA256
    assert module.LOGIN_DIALOG_SIGNATURE == EXPECTED_SIGNATURE
    assert module.LOGIN_DIALOG_NESTED_CALLBACKS == EXPECTED_NESTED

    module_text = MODULE_PATH.read_text(encoding="utf-8")
    module_lines = module_text.splitlines(keepends=True)
    module_tree = ast.parse(module_text)
    functions = top_functions(module_tree, TARGET)
    assert len(functions) == 1, len(functions)
    fn = functions[0]
    source = source_for(module_lines, fn)
    assert fn.end_lineno - fn.lineno + 1 == EXPECTED_LINES
    assert hashlib.sha256(normalized(source).encode("utf-8")).hexdigest() == EXPECTED_SHA256
    assert ast.unparse(fn.args) == EXPECTED_SIGNATURE
    nested = [
        node.name for node in fn.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    assert nested == EXPECTED_NESTED
    calls = sorted({{dotted(node.func) for node in ast.walk(fn) if isinstance(node, ast.Call) and dotted(node.func)}})
    assert calls == module.LOGIN_DIALOG_CALLS

    for node in ast.walk(fn):
        if isinstance(node, ast.Attribute):
            assert not dotted(node).startswith("self.db"), dotted(node)
        if isinstance(node, ast.Call):
            assert dotted(node.func).split(".")[-1].lower() not in FILESYSTEM_MUTATORS, dotted(node.func)
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert not SQL_WRITE_RE.search(node.value), node.value

    desktop_text = DESKTOP.read_text(encoding="utf-8")
    desktop_lines = desktop_text.splitlines(keepends=True)
    desktop_tree = ast.parse(desktop_text)
    assert not top_functions(desktop_tree, TARGET), "original target still present in desktop"

    old = app_method(desktop_tree, "_prompt_login")
    old_source = source_for(desktop_lines, old)
    assert old.end_lineno - old.lineno + 1 == EXPECTED_OLD_LINES
    assert hashlib.sha256(normalized(old_source).encode("utf-8")).hexdigest() == EXPECTED_OLD_SHA256

    imports = [
        node for node in desktop_tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "spina_app.login_dialog_presentation"
    ]
    assert len(imports) == 1, len(imports)
    aliases = {{(alias.name, alias.asname) for alias in imports[0].names}}
    assert ("configure_login_dialog_dependencies", None) in aliases
    assert (TARGET, "_wave45_spina_v32_prompt_login") in aliases

    rebinds = []
    prompt_bindings = []
    role_bindings = []
    for node in ast.walk(desktop_tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        lhs = node.targets[0]
        if isinstance(lhs, ast.Name) and lhs.id == TARGET and isinstance(node.value, ast.Name):
            rebinds.append((node.lineno, node.value.id))
        if (
            isinstance(lhs, ast.Attribute) and isinstance(lhs.value, ast.Name)
            and lhs.value.id == "App" and isinstance(node.value, ast.Name)
        ):
            if lhs.attr == "_prompt_login":
                prompt_bindings.append((node.lineno, node.value.id))
            if lhs.attr == "_prompt_user_role":
                role_bindings.append((node.lineno, node.value.id))
    rebinds.sort(); prompt_bindings.sort(); role_bindings.sort()
    assert len(rebinds) == 1 and rebinds[0][1] == "_wave45_spina_v32_prompt_login", rebinds
    assert prompt_bindings and prompt_bindings[-1][1] == TARGET, prompt_bindings
    assert role_bindings and role_bindings[-1][1] == "_spina_v32_prompt_user_role", role_bindings

    assert "configure_login_dialog_dependencies(globals())" in desktop_text
    assert "import tkinter as tk" in module_text
    assert "from tkinter import messagebox, ttk" in module_text
    print("Wave 45 login-dialog presentation regression passed.")


if __name__ == "__main__":
    main()
'''


def workflow_text() -> str:
    return '''name: Login dialog presentation Wave 45
on:
  pull_request:
    paths:
      - "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
      - "spina_app/login_dialog_presentation.py"
      - "tools/test_login_dialog_presentation_wave_45.py"
      - "tools/test_login_dialog_widget_smoke_wave_45.py"
      - "architecture-map.json"
      - "docs/architecture/**"
      - ".github/workflows/login-dialog-presentation-wave-45.yml"
permissions:
  contents: read
jobs:
  validate:
    runs-on: [self-hosted, Windows, X64]
    timeout-minutes: 45
    steps:
      - name: Check out exact PR head
        uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}
      - name: Compile application, module, and tests
        shell: cmd
        run: |
          python -m py_compile OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py
          python -m py_compile spina_app/login_dialog_presentation.py
          python -m py_compile tools/test_login_dialog_presentation_wave_45.py
          if exist tools/test_login_dialog_widget_smoke_wave_45.py python -m py_compile tools/test_login_dialog_widget_smoke_wave_45.py
          python -m compileall -q spina_app
      - name: Run exact login-dialog regression
        shell: cmd
        run: python tools/test_login_dialog_presentation_wave_45.py
      - name: Run login-dialog Tkinter smoke test
        if: ${{ hashFiles('tools/test_login_dialog_widget_smoke_wave_45.py') != '' }}
        shell: cmd
        run: python tools/test_login_dialog_widget_smoke_wave_45.py
      - name: Validate permanent architecture map
        shell: cmd
        run: python -m tools.test_architecture_map
      - name: Run repository audits
        shell: cmd
        run: |
          if not exist artifacts mkdir artifacts
          python tools/redundancy_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json artifacts/wave-45-redundancy.json
          python tools/spina_quality_audit.py OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py --json artifacts/wave-45-quality.json
      - name: Upload Wave 45 reports
        uses: actions/upload-artifact@v4
        with:
          name: wave-45-reports
          path: artifacts/wave-45-*.json
'''


def main() -> None:
    desktop_text = DESKTOP.read_text(encoding="utf-8")
    tree = ast.parse(desktop_text)
    lines = desktop_text.splitlines(keepends=True)

    target = find_top_function(tree, TARGET)
    source = source_for(lines, target)
    line_count = target.end_lineno - target.lineno + 1
    source_hash = hashlib.sha256(normalized(source).encode("utf-8")).hexdigest()
    if line_count != EXPECTED_LINES:
        raise SystemExit(f"{TARGET} lines changed: {line_count} != {EXPECTED_LINES}")
    if source_hash != EXPECTED_SHA256:
        raise SystemExit(f"{TARGET} hash changed: {source_hash} != {EXPECTED_SHA256}")
    if signature_text(target) != EXPECTED_SIGNATURE:
        raise SystemExit(f"{TARGET} signature changed: {signature_text(target)!r}")
    if direct_nested(target) != EXPECTED_NESTED:
        raise SystemExit(f"{TARGET} callbacks changed: {direct_nested(target)!r}")
    assert_safe(target)

    old = find_app_method(tree, OLD_METHOD)
    old_source = source_for(lines, old)
    old_hash = hashlib.sha256(normalized(old_source).encode("utf-8")).hexdigest()
    old_lines = old.end_lineno - old.lineno + 1
    if old_lines != EXPECTED_OLD_LINES or old_hash != EXPECTED_OLD_SHA256:
        raise SystemExit(f"Original App.{OLD_METHOD} changed: lines={old_lines} hash={old_hash}")

    bindings = runtime_bindings(tree, "_prompt_login")
    if not bindings or bindings[-1][1] != TARGET:
        raise SystemExit(f"Final App._prompt_login binding changed: {bindings!r}")
    role_bindings = runtime_bindings(tree, "_prompt_user_role")
    if not role_bindings or role_bindings[-1][1] != "_spina_v32_prompt_user_role":
        raise SystemExit(f"Final App._prompt_user_role binding changed: {role_bindings!r}")

    replacement = (
        "from spina_app.login_dialog_presentation import (\n"
        "    configure_login_dialog_dependencies,\n"
        "    _spina_v32_prompt_login as _wave45_spina_v32_prompt_login,\n"
        ")\n"
        "configure_login_dialog_dependencies(globals())\n"
        "_spina_v32_prompt_login = _wave45_spina_v32_prompt_login\n"
    )
    new_lines = lines[: target.lineno - 1] + [replacement] + lines[target.end_lineno :]
    DESKTOP.write_text("".join(new_lines), encoding="utf-8")

    calls = calls_for(target)
    MODULE.parent.mkdir(parents=True, exist_ok=True)
    MODULE.write_text(module_text(source, calls), encoding="utf-8")
    TEST.write_text(test_text(), encoding="utf-8")
    WORKFLOW.write_text(workflow_text(), encoding="utf-8")

    print(f"Wave 45 extracted {TARGET}: lines={line_count} hash={source_hash}")
    print(f"Original App.{OLD_METHOD}: lines={old_lines} hash={old_hash}")
    print(f"Final bindings: prompt={bindings[-1]}, role={role_bindings[-1]}")
    print(f"Calls={len(calls)} callbacks={EXPECTED_NESTED}")


if __name__ == "__main__":
    main()
