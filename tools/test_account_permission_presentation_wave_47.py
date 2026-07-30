from __future__ import annotations

import ast
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spina_app.account_permission_presentation import (
    ACCOUNT_PERMISSION_SIGNATURE,
    ACCOUNT_PERMISSION_SOURCE_LINES,
    ACCOUNT_PERMISSION_SOURCE_SHA256,
    ACCOUNT_PERMISSION_TARGET,
    _spina_v32_account_permission_text,
)
from spina_app.features.accounts import (
    account_choices_for_app,
    account_display_name,
    selected_label_for_user_for_app,
)

DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "account_permission_presentation.py"
FEATURE = ROOT / "spina_app" / "features" / "accounts.py"
UI_CONTROLS = ROOT / "spina_app" / "ui_controls.py"
LOGIN_BUTTON_HASH = "5026d5e31401e7dc276a79f2625d117d23133e5e0da643a459e609fd99ff1d59"


def normalized_hash(source: str) -> str:
    normalized = "\n".join(line.rstrip() for line in source.strip().splitlines())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def function_nodes(tree: ast.AST, name: str):
    return [
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]


class Harness:
    def _load_users_db(self):
        return {
            "users": {
                "admin": {"display_name": "Owner Account", "role": "Admin"},
                "other": {"display_name": "Owner Account", "role": "Viewer"},
            }
        }


def main() -> None:
    assert ACCOUNT_PERMISSION_TARGET == "_spina_v32_account_permission_text"
    assert ACCOUNT_PERMISSION_SOURCE_LINES == 11
    assert ACCOUNT_PERMISSION_SOURCE_SHA256 == (
        "d5505320cff939e064d9e85d4e8fc26ec4abe7d5b4f08852cf31d0b703abc6e4"
    )
    assert ACCOUNT_PERMISSION_SIGNATURE == "role"

    module_text = MODULE.read_text(encoding="utf-8")
    module_tree = ast.parse(module_text)
    matches = function_nodes(module_tree, ACCOUNT_PERMISSION_TARGET)
    assert len(matches) == 1
    source = ast.get_source_segment(module_text, matches[0])
    assert source is not None
    assert matches[0].end_lineno - matches[0].lineno + 1 == ACCOUNT_PERMISSION_SOURCE_LINES
    assert ast.unparse(matches[0].args) == ACCOUNT_PERMISSION_SIGNATURE
    assert normalized_hash(source) == ACCOUNT_PERMISSION_SOURCE_SHA256

    desktop_text = DESKTOP.read_text(encoding="utf-8")
    desktop_tree = ast.parse(desktop_text)
    for removed in (
        ACCOUNT_PERMISSION_TARGET,
        "_spina_v32_account_choices",
        "_spina_v32_selected_label_for_user",
        "_spina_v32_account_display_name",
    ):
        assert not function_nodes(desktop_tree, removed), removed

    feature_text = FEATURE.read_text(encoding="utf-8")
    feature_tree = ast.parse(feature_text)
    imports = [
        node for node in feature_tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "spina_app.account_permission_presentation"
    ]
    assert len(imports) == 1
    assert any(alias.name == ACCOUNT_PERMISSION_TARGET for alias in imports[0].names)
    for name in (
        "account_display_name",
        "account_choices_for_app",
        "selected_label_for_user_for_app",
    ):
        assert len(function_nodes(feature_tree, name)) == 1

    ui_text = UI_CONTROLS.read_text(encoding="utf-8")
    ui_tree = ast.parse(ui_text)
    button = function_nodes(ui_tree, "_spina_v32_login_button")
    assert len(button) == 1
    button_source = ast.get_source_segment(ui_text, button[0])
    assert button_source is not None
    assert normalized_hash(button_source) == LOGIN_BUTTON_HASH

    harness = Harness()
    choices, mapping = account_choices_for_app(harness)
    assert choices == ["Owner Account", "Owner Account 2"]
    assert mapping["Owner Account"] == "admin"
    assert mapping["Owner Account 2"] == "other"
    assert selected_label_for_user_for_app(
        harness, "other", choices, mapping
    ) == "Owner Account 2"
    assert account_display_name(harness, "admin") == "Owner Account"

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
        assert _spina_v32_account_permission_text(role) == summary
    print("Wave 47 account permission presentation regression passed.")


if __name__ == "__main__":
    main()
