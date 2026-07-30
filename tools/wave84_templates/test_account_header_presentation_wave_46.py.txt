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
MODULE_PATH = ROOT / "spina_app" / "account_header_presentation.py"
FEATURE_PATH = ROOT / "spina_app" / "features" / "accounts.py"
REFRESH = "_spina_v32_refresh_user_header"
BUILD = "_spina_v32_build_header"
EXPECTED_LINES = {REFRESH: 14, BUILD: 12}
EXPECTED_HASHES = {
    REFRESH: "01feaa575f128e605ab8bb143c208503cad6868103591d9fe72b108045c88f5a",
    BUILD: "ff46e61d0f56a1432ca0d4e4e5257936ff3ba150a84d5b43b254e98424368bac",
}
EXPECTED_SIGNATURES = {REFRESH: "self", BUILD: "self, *args, **kwargs"}
EXPECTED_CALLS = {
    REFRESH: [
        "_log_suppressed_once",
        "_spina_v32_account_display_name",
        "getattr",
        "self._refresh_header_theme",
        "self.user_role_label.config",
    ],
    BUILD: [
        "_spina_v32_orig_build_header",
        "getattr",
        "self._refresh_user_header",
        "self.switch_account_btn.configure",
    ],
}
SQL_WRITE_RE = re.compile(
    r"\b(?:INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|ALTER\s+TABLE|"
    r"DROP\s+TABLE|CREATE\s+TABLE)\b",
    re.I,
)


def normalized(text: str) -> str:
    return "\n".join(
        line.rstrip() for line in textwrap.dedent(text).strip().splitlines()
    ) + "\n"


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def signature_text(fn: ast.FunctionDef) -> str:
    return ast.unparse(fn.args)


def source_for(lines: list[str], node: ast.AST) -> str:
    return "\n".join(lines[node.lineno - 1 : node.end_lineno])


def function_defs(tree: ast.AST, name: str):
    return [
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]


def app_methods(tree: ast.Module, name: str):
    app = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "App"
    )
    return [
        node for node in app.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]


def check_function(fn: ast.FunctionDef, lines: list[str], name: str) -> None:
    source = source_for(lines, fn)
    assert len(textwrap.dedent(source).splitlines()) == EXPECTED_LINES[name]
    assert hashlib.sha256(normalized(source).encode()).hexdigest() == EXPECTED_HASHES[name]
    assert signature_text(fn) == EXPECTED_SIGNATURES[name]
    nested = [
        node.name for node in ast.walk(fn)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node is not fn
    ]
    assert nested == []
    calls = sorted({
        dotted(node.func)
        for node in ast.walk(fn)
        if isinstance(node, ast.Call) and dotted(node.func)
    })
    assert calls == EXPECTED_CALLS[name]
    for node in ast.walk(fn):
        if isinstance(node, ast.Attribute):
            assert not dotted(node).startswith("self.db")
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert not SQL_WRITE_RE.search(node.value)


def main() -> None:
    module = importlib.import_module("spina_app.account_header_presentation")
    assert module.ACCOUNT_HEADER_TARGETS == [REFRESH, BUILD]
    assert module.ACCOUNT_HEADER_SOURCE_LINES == EXPECTED_LINES
    assert module.ACCOUNT_HEADER_SOURCE_SHA256 == EXPECTED_HASHES
    assert module.ACCOUNT_HEADER_SIGNATURES == EXPECTED_SIGNATURES
    assert module.ACCOUNT_HEADER_NESTED_CALLBACKS == {REFRESH: [], BUILD: []}
    assert module.ACCOUNT_HEADER_CALLS == EXPECTED_CALLS

    module_text = MODULE_PATH.read_text(encoding="utf-8")
    module_lines = module_text.splitlines()
    module_tree = ast.parse(module_text)
    for name in (REFRESH, BUILD):
        defs = function_defs(module_tree, name)
        assert len(defs) == 1
        check_function(defs[0], module_lines, name)

    desktop_text = DESKTOP.read_text(encoding="utf-8")
    desktop_tree = ast.parse(desktop_text)
    assert not function_defs(desktop_tree, REFRESH)
    assert not function_defs(desktop_tree, BUILD)
    assert not app_methods(desktop_tree, "_refresh_user_header")
    assert not app_methods(desktop_tree, "switch_account")
    assert not function_defs(desktop_tree, "_spina_v32_switch_account")

    imports = [
        node for node in desktop_tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "spina_app.account_header_presentation"
    ]
    assert len(imports) == 1
    aliases = {(alias.name, alias.asname) for alias in imports[0].names}
    assert (
        "configure_account_header_dependencies",
        "_wave46_configure_account_header_dependencies",
    ) in aliases
    assert len(aliases) == 1

    original_marker = '_spina_v32_orig_build_header = getattr(App, "_build_header", None)'
    configure_marker = "_wave46_configure_account_header_dependencies(globals())"
    assert desktop_text.count(original_marker) == 1
    assert desktop_text.count(configure_marker) == 1
    assert desktop_text.index(original_marker) < desktop_text.index(configure_marker)

    feature_text = FEATURE_PATH.read_text(encoding="utf-8")
    feature_tree = ast.parse(feature_text)
    installer = function_defs(feature_tree, "install_accounts_feature")
    assert len(installer) == 1
    installer_source = ast.get_source_segment(feature_text, installer[0]) or ""
    for token in (
        "app_class.switch_account = switch_account",
        "app_class._refresh_user_header = refresh_header",
        "app_class._build_header = build_header",
    ):
        assert token in installer_source

    configure = function_defs(module_tree, "configure_account_header_dependencies")
    assert len(configure) == 1
    configure_source = ast.get_source_segment(module_text, configure[0]) or ""
    assert "install_accounts_feature(" in configure_source
    assert "account_display_name" in configure_source
    print("Wave 46 account header presentation regression passed.")


if __name__ == "__main__":
    main()
