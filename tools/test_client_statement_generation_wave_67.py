from __future__ import annotations

import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "client_statement_generation.py"
EXPECTED_LINES = 258
EXPECTED_SOURCE_SHA = "8225a64ebbaf150af577a34f185fafbef8d4310d56132a45a86e53acebe5e2df"
EXPECTED_SIGNATURE = "self"
EXPECTED_DB_CALLS = ["self.db.get_client_info", "self.db.get_client_link_meta"]


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
        if isinstance(n, ast.FunctionDef) and n.name == "generate_pdf_selected"
    )
    lines = module_text.splitlines(keepends=True)
    source = "".join(lines[function.lineno - 1:function.end_lineno])

    namespace = {}
    exec(compile(module_text, str(MODULE), "exec"), namespace)
    metadata = namespace["CLIENT_STATEMENT_GENERATION_METHODS"]["generate_pdf_selected"]

    assert function.end_lineno - function.lineno + 1 == EXPECTED_LINES
    assert metadata["lines"] == EXPECTED_LINES
    assert metadata["source_sha256"] == EXPECTED_SOURCE_SHA
    assert sha(source) == metadata["dedented_sha256"]
    assert ast.unparse(function.args) == EXPECTED_SIGNATURE == metadata["signature"]

    calls = sorted({dotted(c.func) for c in ast.walk(function) if isinstance(c, ast.Call) and dotted(c.func)})
    db_calls = sorted(c for c in calls if c.startswith("self.db") or ".db." in c)
    assert calls == metadata["calls"]
    assert db_calls == EXPECTED_DB_CALLS == metadata["db_calls"]
    assert not any(term in call.lower() for call in db_calls for term in (
        "add", "insert", "update", "delete", "save", "commit", "rollback",
    ))

    app_text = APP.read_text(encoding="utf-8")
    app_tree = ast.parse(app_text)
    app = next(n for n in app_tree.body if isinstance(n, ast.ClassDef) and n.name == "App")
    assert not any(
        isinstance(n, ast.FunctionDef) and n.name == "generate_pdf_selected"
        for n in app.body
    )
    assert app_text.count(
        "configure_client_statement_generation_dependencies as _configure_wave67_client_statement_generation"
    ) == 1
    assert app_text.count("_configure_wave67_client_statement_generation(globals())") == 1
    assert app_text.count("App.generate_pdf_selected = _wave67_generate_pdf_selected") == 1

    # Wave 67 delegates background execution to the Wave 42 extracted helper.
    assert "_configure_wave42_long_task(globals())" in app_text
    assert "App._run_long_task = _wave42_run_long_task" in app_text
    print("Wave 67 client-statement generation structural regression passed")


if __name__ == "__main__":
    main()
