from __future__ import annotations

import ast
import hashlib
import sys
from pathlib import Path

_TEST_ROOT = Path(__file__).resolve().parents[1]
if str(_TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(_TEST_ROOT))

from spina_app.account_permission_presentation import (
    ACCOUNT_PERMISSION_SIGNATURE,
    ACCOUNT_PERMISSION_SOURCE_LINES,
    ACCOUNT_PERMISSION_SOURCE_SHA256,
    ACCOUNT_PERMISSION_TARGET,
    _spina_v32_account_permission_text,
)

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "account_permission_presentation.py"
UI_CONTROLS = ROOT / "spina_app" / "ui_controls.py"
CALLER_HASHES = {
    "_spina_v32_account_choices": "25bbe162bb3b2d771ee913f73b9c3c2e98b73375b5737ed01bb7c5ac8334f280",
    "_spina_v32_selected_label_for_user": "8b775aa3feb95037083709047367c8fe06c485a1521906aada4fee97d0b8564c",
    "_spina_v32_account_display_name": "91d6223b1850845e6c28b1e6aae340136cb6128c93b963690ab7c69d01d18135",
    "_spina_v32_login_button": "5026d5e31401e7dc276a79f2625d117d23133e5e0da643a459e609fd99ff1d59",
}
CALLER_PATHS = {
    "_spina_v32_account_choices": DESKTOP,
    "_spina_v32_selected_label_for_user": DESKTOP,
    "_spina_v32_account_display_name": DESKTOP,
    "_spina_v32_login_button": UI_CONTROLS,
}


def normalized_hash(source: str) -> str:
    normalized = "\n".join(line.rstrip() for line in source.strip().splitlines())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def function_nodes(tree: ast.AST, name: str):
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]


def main() -> None:
    assert ACCOUNT_PERMISSION_TARGET == "_spina_v32_account_permission_text"
    assert ACCOUNT_PERMISSION_SOURCE_LINES == 11
    assert ACCOUNT_PERMISSION_SOURCE_SHA256 == "d5505320cff939e064d9e85d4e8fc26ec4abe7d5b4f08852cf31d0b703abc6e4"
    assert ACCOUNT_PERMISSION_SIGNATURE == "role"

    module_text = MODULE.read_text(encoding="utf-8")
    module_tree = ast.parse(module_text)
    module_matches = function_nodes(module_tree, ACCOUNT_PERMISSION_TARGET)
    assert len(module_matches) == 1
    module_node = module_matches[0]
    module_source = ast.get_source_segment(module_text, module_node)
    assert module_source is not None
    assert module_node.end_lineno - module_node.lineno + 1 == ACCOUNT_PERMISSION_SOURCE_LINES
    assert ast.unparse(module_node.args) == ACCOUNT_PERMISSION_SIGNATURE
    assert normalized_hash(module_source) == ACCOUNT_PERMISSION_SOURCE_SHA256

    desktop_text = DESKTOP.read_text(encoding="utf-8")
    desktop_tree = ast.parse(desktop_text)
    assert not function_nodes(desktop_tree, ACCOUNT_PERMISSION_TARGET)

    imports = [
        node
        for node in ast.walk(desktop_tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "spina_app.account_permission_presentation"
    ]
    assert len(imports) == 1
    aliases = imports[0].names
    assert len(aliases) == 1
    assert aliases[0].name == ACCOUNT_PERMISSION_TARGET
    assert aliases[0].asname == "_wave47_spina_v32_account_permission_text"

    assignments = [
        node
        for node in ast.walk(desktop_tree)
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == ACCOUNT_PERMISSION_TARGET
    ]
    assert len(assignments) == 1
    assert isinstance(assignments[0].value, ast.Name)
    assert assignments[0].value.id == "_wave47_spina_v32_account_permission_text"

    loaded: dict[Path, tuple[str, ast.Module]] = {DESKTOP: (desktop_text, desktop_tree)}
    for name, expected_hash in CALLER_HASHES.items():
        path = CALLER_PATHS[name]
        if path not in loaded:
            text = path.read_text(encoding="utf-8")
            loaded[path] = (text, ast.parse(text))
        text, tree = loaded[path]
        matches = function_nodes(tree, name)
        assert len(matches) == 1, (path.name, name, len(matches))
        source = ast.get_source_segment(text, matches[0])
        assert source is not None
        assert normalized_hash(source) == expected_hash, (path.name, name)

    expected = {
        "Admin": "Full app access",
        "Encoder": "Encoding, reports, and route access",
        "Viewer": "Reports access",
        "System": "Audit, controls, and system tools",
        "Manager": "Custom account access",
        "admin": "Custom account access",
        "": "Custom account access",
        None: "Custom account access",
    }
    for role, summary in expected.items():
        assert _spina_v32_account_permission_text(role) == summary, (role, summary)

    print("Wave 47 account permission presentation regression passed.")


if __name__ == "__main__":
    main()
