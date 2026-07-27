"""Exact-source regression for Wave 57 Data Bank Close History presentation."""
from __future__ import annotations

import ast
import hashlib
import inspect
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"


def main() -> None:
    import spina_app.databank_close_history_presentation as module

    assert module.CLOSE_HISTORY_PRESENTATION_TARGET == 'open_databank_close_history_dialog'
    assert module.CLOSE_HISTORY_PRESENTATION_SOURCE_LINES == 71
    assert module.CLOSE_HISTORY_PRESENTATION_SOURCE_SHA256 == 'b08b9c7f4afe8513597a0ec0f0814a92e2bbd816b2ff06fcdc488da39eabfeed'
    assert module.CLOSE_HISTORY_PRESENTATION_DEDENTED_SHA256 == '47e55f4f4b23dd1f27571c390e4425a995a5f877a6bde08a7bc12e461e39e6b3'
    assert module.CLOSE_HISTORY_PRESENTATION_SIGNATURE == 'self, date_s, loan_type=None'
    assert module.CLOSE_HISTORY_PRESENTATION_CALLS == ['abs', 'anchors.get', 'float', 'fmt_currency', 'grid', 'hasattr', 'headings.get', 'hsb.grid', 'outer.columnconfigure', 'outer.pack', 'outer.rowconfigure', 'rec.get', 'self.db.list_databank_day_close_history', 'strip', 'tk.Toplevel', 'top.geometry', 'top.grab_set', 'top.title', 'top.transient', 'tree.column', 'tree.configure', 'tree.grid', 'tree.heading', 'tree.insert', 'ttk.Button', 'ttk.Frame', 'ttk.Label', 'ttk.Scrollbar', 'ttk.Treeview', 'vsb.grid', 'widths.get']
    assert module.CLOSE_HISTORY_PRESENTATION_DB_CALLS == ["self.db.list_databank_day_close_history"]

    module_source = inspect.getsource(module.open_databank_close_history_dialog)
    assert len(module_source.splitlines()) == 71
    assert hashlib.sha256(module_source.encode("utf-8")).hexdigest() == module.CLOSE_HISTORY_PRESENTATION_DEDENTED_SHA256

    app_text = APP.read_text(encoding="utf-8-sig")
    tree = ast.parse(app_text, filename=str(APP))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "App":
            assert not any(
                isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                and child.name == 'open_databank_close_history_dialog'
                for child in node.body
            )

    assert app_text.count("_configure_wave57_close_history_presentation(globals())") == 1
    assert app_text.count("App.open_databank_close_history_dialog = _wave57_open_databank_close_history_dialog") == 1
    lowered = "\n".join(module.CLOSE_HISTORY_PRESENTATION_CALLS).lower()
    assert not [fragment for fragment in ('.execute', '.executemany', '.commit', '.rollback', 'set_databank_day_close', 'replace_databank_day_collectors', 'delete_transactions_for_day', 'delete_transaction', 'add_or_update_transaction', 'close_day', 'reopen_day', 'backup', 'restore', 'password', 'write_text', 'write_bytes', 'unlink') if fragment in lowered]
    print("Wave 57 exact Data Bank Close History extraction regression passed")


if __name__ == "__main__":
    main()
