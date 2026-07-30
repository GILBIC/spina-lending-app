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
MODULE_PATH = ROOT / "spina_app" / "login_dialog_presentation.py"
FEATURE_PATH = ROOT / "spina_app" / "features" / "accounts.py"
TARGET = "_spina_v32_prompt_login"
EXPECTED_LINES = 234
EXPECTED_SHA256 = "0dc7c87e702bf93da77bbf6a9fc490a005114716e4ef487f10a203bfe75e48a3"
EXPECTED_SIGNATURE = "self, default_user: str='admin'"
EXPECTED_NESTED = ["_toggle_show", "_refresh_account_info", "_ok", "_cancel", "_enter"]
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


def top_functions(tree: ast.Module, name: str):
    return [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]


def class_methods(tree: ast.Module, name: str) -> list[ast.FunctionDef]:
    app = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "App"
    )
    return [
        node for node in app.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]


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
    assert len(functions) == 1
    fn = functions[0]
    source = source_for(module_lines, fn)
    assert fn.end_lineno - fn.lineno + 1 == EXPECTED_LINES
    assert hashlib.sha256(normalized(source).encode("utf-8")).hexdigest() == EXPECTED_SHA256
    assert ast.unparse(fn.args) == EXPECTED_SIGNATURE
    assert [
        node.name for node in fn.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ] == EXPECTED_NESTED
    assert sorted({
        dotted(node.func)
        for node in ast.walk(fn)
        if isinstance(node, ast.Call) and dotted(node.func)
    }) == module.LOGIN_DIALOG_CALLS

    for node in ast.walk(fn):
        if isinstance(node, ast.Attribute):
            assert not dotted(node).startswith("self.db"), dotted(node)
        if isinstance(node, ast.Call):
            assert dotted(node.func).split(".")[-1].lower() not in FILESYSTEM_MUTATORS
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert not SQL_WRITE_RE.search(node.value)

    desktop_text = DESKTOP.read_text(encoding="utf-8")
    desktop_tree = ast.parse(desktop_text)
    assert not top_functions(desktop_tree, TARGET)
    assert not class_methods(desktop_tree, "_prompt_login")
    assert not class_methods(desktop_tree, "_prompt_user_role")
    for obsolete in (
        "_spina_v32_account_choices",
        "_spina_v32_selected_label_for_user",
        "_spina_v32_make_users_account_based",
        "_spina_v32_prompt_user_role",
        "_spina_v32_switch_account",
    ):
        assert not top_functions(desktop_tree, obsolete), obsolete

    feature_text = FEATURE_PATH.read_text(encoding="utf-8")
    feature_tree = ast.parse(feature_text)
    assert len(top_functions(feature_tree, "install_accounts_feature")) == 1
    assert len(top_functions(feature_tree, "_configure_login_presentation")) == 1
    installer = top_functions(feature_tree, "install_accounts_feature")[0]
    assignments = {
        dotted(node.targets[0]): dotted(node.value)
        for node in ast.walk(installer)
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
    }
    assert assignments["app_class._prompt_login"] == "prompt_login"
    assert assignments["app_class._prompt_user_role"] == "prompt_user_role"
    assert 'from spina_app.login_dialog_presentation import _spina_v32_prompt_login' in feature_text
    assert "configure_login_dialog_dependencies(dependencies)" in feature_text

    assert desktop_text.count("# --- BEGIN: v32 Modern Account-Based Login ---") == 1
    assert desktop_text.count("_wave46_configure_account_header_dependencies(globals())") == 1
    assert "configure_login_dialog_dependencies(globals())" not in desktop_text
    print("Wave 45 login-dialog presentation regression passed.")


if __name__ == "__main__":
    main()
