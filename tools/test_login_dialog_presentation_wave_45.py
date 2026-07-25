from __future__ import annotations

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
TARGET = '_spina_v32_prompt_login'
EXPECTED_LINES = 234
EXPECTED_SHA256 = '0dc7c87e702bf93da77bbf6a9fc490a005114716e4ef487f10a203bfe75e48a3'
EXPECTED_SIGNATURE = "self, default_user: str='admin'"
EXPECTED_NESTED = ['_toggle_show', '_refresh_account_info', '_ok', '_cancel', '_enter']
EXPECTED_OLD_LINES = 126
EXPECTED_OLD_SHA256 = '095ec5385a973531328c2dbc57c45fef867b2b422bd1713f3677dcc2bc30e75d'
SQL_WRITE_RE = re.compile(r"\b(?:INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|REPLACE\s+INTO|ALTER\s+TABLE|DROP\s+TABLE|CREATE\s+TABLE|TRUNCATE\s+TABLE)\b", re.I)
FILESYSTEM_MUTATORS = {"write", "write_text", "write_bytes", "unlink", "remove", "rmtree", "rename", "replace", "mkdir", "makedirs", "dump", "dumps"}


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
    calls = sorted({dotted(node.func) for node in ast.walk(fn) if isinstance(node, ast.Call) and dotted(node.func)})
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
    aliases = {(alias.name, alias.asname) for alias in imports[0].names}
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
