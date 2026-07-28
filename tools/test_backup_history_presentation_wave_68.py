from __future__ import annotations

import ast
import hashlib
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "backup_history_presentation.py"
EXPECTED_LINES = 182
EXPECTED_SOURCE_SHA = "c05501298b2aa308c66f0f668bb482a96de8dc221b098f88705fa6d452c6d59f"
EXPECTED_SIGNATURE = "self"


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
    function = next(
        n for n in module_tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "open_backup_history_window"
    )
    lines = module_text.splitlines(keepends=True)
    source = "".join(lines[function.lineno - 1:function.end_lineno])

    namespace = {}
    exec(compile(module_text, str(MODULE), "exec"), namespace)
    metadata = namespace["BACKUP_HISTORY_PRESENTATION_METHODS"]["open_backup_history_window"]

    assert function.end_lineno - function.lineno + 1 == EXPECTED_LINES
    assert metadata["lines"] == EXPECTED_LINES
    assert metadata["source_sha256"] == EXPECTED_SOURCE_SHA
    assert sha(source) == metadata["dedented_sha256"]
    assert sha(textwrap.indent(source, "    ")) == EXPECTED_SOURCE_SHA
    assert ast.unparse(function.args) == EXPECTED_SIGNATURE == metadata["signature"]

    calls = sorted({
        dotted(item.func)
        for item in ast.walk(function)
        if isinstance(item, ast.Call) and dotted(item.func)
    })
    db_calls = sorted(c for c in calls if c.startswith("self.db") or ".db." in c)
    assert calls == metadata["calls"]
    assert db_calls == [] == metadata["db_calls"]
    assert "self._verify_postgres_backup_file" in calls
    assert "self._restore_backup_to_test_database" in calls
    assert "self._run_long_task" in calls
    assert "spina_restore_test" in module_text
    assert "self.db" not in module_text

    app_text = APP.read_text(encoding="utf-8")
    app_tree = ast.parse(app_text)
    app = next(n for n in app_tree.body if isinstance(n, ast.ClassDef) and n.name == "App")
    assert not any(
        isinstance(n, ast.FunctionDef) and n.name == "open_backup_history_window"
        for n in app.body
    )
    assert app_text.count(
        "configure_backup_history_dependencies as _configure_wave68_backup_history"
    ) == 1
    assert app_text.count("_configure_wave68_backup_history(globals())") == 1
    assert app_text.count(
        "App.open_backup_history_window = _wave68_open_backup_history_window"
    ) == 1
    assert "App._run_long_task = _wave42_run_long_task" in app_text
    print("Wave 68 backup-history structural regression passed")


if __name__ == "__main__":
    main()
