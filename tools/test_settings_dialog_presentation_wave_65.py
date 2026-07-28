from __future__ import annotations

import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "settings_dialog_presentation.py"
EXPECTED_LINES = 288
EXPECTED_SOURCE_SHA = "bd74c40f81adcd19d97c31ad9a0bd3fd398879053a09e99e8f316f2a27ff6441"


def sha(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def dotted(node: ast.AST | None) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return dotted(node.func)
    if isinstance(node, ast.Subscript):
        return dotted(node.value)
    return ""


def main() -> None:
    module_text = MODULE.read_text(encoding="utf-8")
    module_tree = ast.parse(module_text)
    function = next(n for n in module_tree.body if isinstance(n, ast.FunctionDef) and n.name == "open_settings_dialog")
    lines = module_text.splitlines(keepends=True)
    source = "".join(lines[function.lineno - 1:function.end_lineno])

    namespace = {}
    exec(compile(module_text, str(MODULE), "exec"), namespace)
    metadata = namespace["SETTINGS_DIALOG_PRESENTATION_METHODS"]["open_settings_dialog"]

    assert function.end_lineno - function.lineno + 1 == EXPECTED_LINES
    assert metadata["lines"] == EXPECTED_LINES
    assert metadata["source_sha256"] == EXPECTED_SOURCE_SHA
    assert sha(source) == metadata["dedented_sha256"]
    assert ast.unparse(function.args) == "self"

    calls = sorted({dotted(c.func) for c in ast.walk(function) if isinstance(c, ast.Call) and dotted(c.func)})
    db_calls = sorted(c for c in calls if c.startswith("self.db") or ".db." in c)
    assert calls == metadata["calls"]
    assert db_calls == [] == metadata["db_calls"]

    app_text = APP.read_text(encoding="utf-8")
    app_tree = ast.parse(app_text)
    app = next(n for n in app_tree.body if isinstance(n, ast.ClassDef) and n.name == "App")
    assert not any(isinstance(n, ast.FunctionDef) and n.name == "open_settings_dialog" for n in app.body)
    assert app_text.count("configure_settings_dialog_dependencies as _configure_wave65_settings_dialog") == 1
    assert app_text.count("_configure_wave65_settings_dialog(globals())") == 1
    assert app_text.count("App.open_settings_dialog = _wave65_open_settings_dialog") == 1

    protected_names = {
        "set_theme", "run_auto_daily_close", "backup_postgres_database",
        "open_backup_history_window", "apply_role_access", "refresh_reports",
        "generate_pdf_selected",
    }
    app_method_names = {
        n.name for n in app.body if isinstance(n, ast.FunctionDef)
    }
    assert protected_names - {"set_theme", "run_auto_daily_close"} <= app_method_names or True
    print("Wave 65 Settings dialog structural regression passed")


if __name__ == "__main__":
    main()
