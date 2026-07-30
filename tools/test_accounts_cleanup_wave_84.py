#!/usr/bin/env python3
"""Architecture regression for redundant account cleanup Wave 84."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
FEATURE = ROOT / "spina_app" / "features" / "accounts.py"

REMOVED_APP_METHODS = {
    "_prompt_login",
    "_prompt_user_role",
    "_refresh_user_header",
    "switch_account",
}
REMOVED_TOP_LEVEL = {
    "_spina_v32_account_default_name",
    "_spina_v32_account_display_name",
    "_spina_v32_account_role",
    "_spina_v32_account_choices",
    "_spina_v32_selected_label_for_user",
    "_spina_v32_make_users_account_based",
    "_spina_v32_switch_account",
    "_spina_v32_prompt_user_role",
}


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def main() -> None:
    text = DESKTOP.read_text(encoding="utf-8")
    tree = ast.parse(text)
    app = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "App"
    )
    methods = {
        node.name for node in app.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert not (methods & REMOVED_APP_METHODS), methods & REMOVED_APP_METHODS

    top_functions = {
        node.name for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert not (top_functions & REMOVED_TOP_LEVEL), top_functions & REMOVED_TOP_LEVEL

    assert text.count("# --- BEGIN: v32 Modern Account-Based Login ---") == 1
    assert text.count("# --- END: v32 Modern Account-Based Login ---") == 1
    assert text.count("_wave46_configure_account_header_dependencies(globals())") == 1
    assert 'from spina_app.ui_controls import _spina_v32_login_button' in text
    assert "configure_login_dialog_dependencies(globals())" not in text
    assert "App._load_users_db = _spina_v32_make_users_account_based" not in text
    assert "App.switch_account = _spina_v32_switch_account" not in text

    direct_account_bindings = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = dotted(node.targets[0])
        if target in {
            "App._load_users_db",
            "App._prompt_login",
            "App._prompt_user_role",
            "App._refresh_user_header",
            "App.switch_account",
            "App._build_header",
        }:
            direct_account_bindings.append(target)
    assert not direct_account_bindings, direct_account_bindings

    feature_text = FEATURE.read_text(encoding="utf-8")
    feature_tree = ast.parse(feature_text)
    installer = next(
        node for node in feature_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "install_accounts_feature"
    )
    source = ast.get_source_segment(feature_text, installer) or ""
    for token in (
        "app_class._load_users_db = load_users_account_based",
        "app_class._prompt_login = prompt_login",
        "app_class._prompt_user_role = prompt_user_role",
        "app_class.switch_account = switch_account",
        "app_class._refresh_user_header = refresh_header",
        "app_class._build_header = build_header",
    ):
        assert token in source, token
    print("Wave 84 redundant account cleanup regression passed.")


if __name__ == "__main__":
    main()
