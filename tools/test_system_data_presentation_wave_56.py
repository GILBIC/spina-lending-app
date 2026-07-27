"""Exact-source regression for Wave 56 System Data presentation."""
from __future__ import annotations

import ast
import hashlib
import inspect
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"


def main() -> None:
    import spina_app.system_data_presentation as module

    assert module.SYSTEM_DATA_PRESENTATION_TARGET == '_build_system_data_tab'
    assert module.SYSTEM_DATA_PRESENTATION_SOURCE_LINES == 46
    assert module.SYSTEM_DATA_PRESENTATION_SOURCE_SHA256 == 'b4d8ff8e73daca66a7aa4d6d5e8e08fe5d91648f04c7a2e485fb0677add79f3d'
    assert module.SYSTEM_DATA_PRESENTATION_DEDENTED_SHA256 == '3bc94f4af5ae75cc1a287f262e4c647d9d929a0906ebe73318f167dd472a119b'
    assert module.SYSTEM_DATA_PRESENTATION_SIGNATURE == 'self'
    assert module.SYSTEM_DATA_PRESENTATION_CALLS == ['_dt.now', '_log_suppressed_once', 'controls.columnconfigure', 'controls.grid', 'grid', 'outer.columnconfigure', 'outer.rowconfigure', 'range', 'self._get_databank_focus_date', 'self._system_data_refresh_summary', 'strftime', 'summary.columnconfigure', 'summary.grid', 'summary.rowconfigure', 'title.columnconfigure', 'title.grid', 'tk.StringVar', 'ttk.Button', 'ttk.Entry', 'ttk.Frame', 'ttk.Label', 'ttk.LabelFrame']

    module_source = inspect.getsource(module._build_system_data_tab)
    assert len(module_source.splitlines()) == 46
    assert hashlib.sha256(module_source.encode("utf-8")).hexdigest() == module.SYSTEM_DATA_PRESENTATION_DEDENTED_SHA256

    app_text = APP.read_text(encoding="utf-8-sig")
    tree = ast.parse(app_text, filename=str(APP))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "App":
            assert not any(isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == '_build_system_data_tab' for child in node.body)

    assert app_text.count("_configure_wave56_system_data_presentation(globals())") == 1
    assert app_text.count("App._build_system_data_tab = _wave56_build_system_data_tab") == 1
    lowered = "\n".join(module.SYSTEM_DATA_PRESENTATION_CALLS).lower()
    assert not [fragment for fragment in ('.execute', '.executemany', '.commit', '.rollback', 'insert', 'delete_transaction', 'update_transaction', 'set_transaction', 'add_transaction', 'close_day', 'reopen_day', 'backup', 'restore', 'password', 'pg_dump', 'unlink', 'write_text', 'write_bytes') if fragment in lowered]
    print("Wave 56 exact System Data extraction regression passed")


if __name__ == "__main__":
    main()
