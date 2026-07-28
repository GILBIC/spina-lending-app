from __future__ import annotations

import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "databank_close_records_presentation.py"
EXPECTED_LINES = 224
EXPECTED_SOURCE_SHA = "2b3050213b1861f3b0a085742a1b9d277dd0cb2999337b8f5df83fc832435c74"
EXPECTED_SIGNATURE = "self, start_date=None, end_date=None"
EXPECTED_DB_CALLS = ["self.db.list_databank_day_close_records"]


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
        if isinstance(n, ast.FunctionDef) and n.name == "open_databank_close_records_dialog"
    )
    lines = module_text.splitlines(keepends=True)
    source = "".join(lines[function.lineno - 1:function.end_lineno])

    namespace = {}
    exec(compile(module_text, str(MODULE), "exec"), namespace)
    metadata = namespace["DATABANK_CLOSE_RECORDS_PRESENTATION_METHODS"]["open_databank_close_records_dialog"]

    assert function.end_lineno - function.lineno + 1 == EXPECTED_LINES
    assert metadata["lines"] == EXPECTED_LINES
    assert metadata["source_sha256"] == EXPECTED_SOURCE_SHA
    assert sha(source) == metadata["dedented_sha256"]
    assert ast.unparse(function.args) == EXPECTED_SIGNATURE == metadata["signature"]

    calls = sorted({dotted(c.func) for c in ast.walk(function) if isinstance(c, ast.Call) and dotted(c.func)})
    db_calls = sorted(c for c in calls if c.startswith("self.db") or ".db." in c)
    assert calls == metadata["calls"]
    assert db_calls == EXPECTED_DB_CALLS == metadata["db_calls"]
    assert not any(term in call.lower() for call in db_calls for term in ("add", "insert", "update", "delete", "save", "commit", "rollback"))

    app_text = APP.read_text(encoding="utf-8")
    app_tree = ast.parse(app_text)
    app = next(n for n in app_tree.body if isinstance(n, ast.ClassDef) and n.name == "App")
    assert not any(
        isinstance(n, ast.FunctionDef) and n.name == "open_databank_close_records_dialog"
        for n in app.body
    )
    assert app_text.count("configure_databank_close_records_dependencies as _configure_wave66_databank_close_records") == 1
    assert app_text.count("_configure_wave66_databank_close_records(globals())") == 1
    assert app_text.count("App.open_databank_close_records_dialog = _wave66_open_databank_close_records_dialog") == 1

    remaining = {n.name for n in app.body if isinstance(n, ast.FunctionDef)}
    assert "open_databank_close_dialog" in remaining
    assert "print_databank_close_report" in remaining
    print("Wave 66 Data Bank close-records structural regression passed")


if __name__ == "__main__":
    main()
