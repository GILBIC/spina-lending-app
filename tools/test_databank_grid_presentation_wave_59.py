"""Exact-source regression for Wave 59 Data Bank grid presentation."""
from __future__ import annotations

import ast
import hashlib
import inspect
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
TARGETS = ("goto_current_month", "prev_month", "next_month", "refresh_data_grid")
PROTECTED_METHODS = (
    "_begin_cell_edit",
    "_save_cell_edit",
    "delete_selected_cell",
    "_mark_missed_for_selected",
    "open_delete_day_dialog",
    "_import_from_excel_entry",
    "open_databank_close_dialog",
)
PROTECTED_MODULES = (
    ROOT / "spina_app" / "databank_editor_presentation.py",
    ROOT / "spina_app" / "databank_cell_writes.py",
    ROOT / "spina_app" / "databank_delete_day.py",
    ROOT / "spina_app" / "databank_feature.py",
)
FORBIDDEN_CALL_MARKERS = (
    ".execute",
    ".executemany",
    ".commit",
    ".rollback",
    "set_databank_day_close",
    "replace_databank_day_collectors",
    "delete_transactions_for_day",
    "delete_transaction",
    "add_or_update_transaction",
    "close_day",
    "reopen_day",
    "backup",
    "restore",
    "write_text",
    "write_bytes",
    "unlink",
)


def dotted(node: ast.AST) -> str:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def function_names(path: Path) -> set[str]:
    if not path.exists():
        return set()
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def main() -> None:
    import spina_app.databank_grid_presentation as module

    metadata = module.DATABANK_GRID_PRESENTATION_METHODS
    assert tuple(metadata) == TARGETS
    assert sum(item["lines"] for item in metadata.values()) == 284

    app_text = APP.read_text(encoding="utf-8-sig")
    app_tree = ast.parse(app_text, filename=str(APP))
    app_class = next(node for node in app_tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    app_methods = {
        child.name
        for child in app_class.body
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    for name in TARGETS:
        expected = metadata[name]
        assert name not in app_methods
        function = getattr(module, name)
        source = inspect.getsource(function)
        assert len(source.splitlines()) == expected["lines"]
        assert hashlib.sha256(source.encode("utf-8")).hexdigest() == expected["dedented_sha256"]
        node = ast.parse(source).body[0]
        assert ast.unparse(node.args) == expected["signature"]
        calls = sorted({
            dotted(call.func)
            for call in ast.walk(node)
            if isinstance(call, ast.Call) and dotted(call.func)
        })
        assert calls == expected["calls"]
        assert [call for call in calls if call.startswith("self.db.")] == expected["db_calls"]
        lowered = "\n".join(calls).lower()
        assert not [marker for marker in FORBIDDEN_CALL_MARKERS if marker in lowered]

    available = set(app_methods)
    for path in PROTECTED_MODULES:
        available.update(function_names(path))
    assert all(name in available for name in PROTECTED_METHODS)

    assert app_text.count("_configure_wave59_databank_grid(globals())") == 1
    for name in TARGETS:
        assert app_text.count(f"App.{name} = _wave59_{name}") == 1

    print("Wave 59 exact Data Bank grid extraction regression passed")


if __name__ == "__main__":
    main()
