from __future__ import annotations

import ast
import hashlib
import importlib.util
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE = ROOT / "spina_app" / "calendar_presentation.py"
TARGETS = ['_CalendarPopup', '_CalendarRangePopup', 'pick_date_range', 'pick_date']
EXPECTED_LINES = {'_CalendarPopup': 129, '_CalendarRangePopup': 196, 'pick_date_range': 44, 'pick_date': 30}
EXPECTED_SHA256 = {'_CalendarPopup': '2b3d53bd8311c04e77e487523032f81f815ddd9042c2561f528fb2d9201a4566', '_CalendarRangePopup': '948417432b06896c6ffe6099ab754837716cff5b85eadbb0ee2294e022dddf3d', 'pick_date_range': '3af01720d3a2295fd618a442abbb1ae814742bf662b954bba85427abee05df45', 'pick_date': '1d19e6cb0141bd22531b37ae48748dac1c24dbde39479c84f3406922820cf9ad'}
EXPECTED_METHODS = {'_CalendarPopup': ['__init__', '_build_ui', '_render', '_pick', '_prev_month', '_next_month', '_today', '_clear', '_close'], '_CalendarRangePopup': ['__init__', '_build_ui', '_render', '_refresh_info', '_pick', '_apply', '_prev_month', '_next_month', '_today', '_clear', '_close']}
FORBIDDEN_CALL_SUFFIXES = ['add_client', 'add_transaction', 'archive_client', 'close_databank_day', 'commit', 'cursor', 'delete_client', 'delete_transaction', 'execute', 'executemany', 'renew_client', 'reopen_databank_day', 'restore_client', 'rollback', 'set_client_note', 'set_transaction', 'update_client', 'update_transaction', 'write', 'write_bytes', 'write_text']
FORBIDDEN_SQL_TOKENS = ('INSERT INTO', 'UPDATE ', 'DELETE FROM', 'CREATE TABLE', 'ALTER TABLE', 'DROP TABLE', 'TRUNCATE TABLE')


def normalized(source):
    return textwrap.dedent(source).strip() + "\n"


def call_chain(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return list(reversed(parts))


def main():
    spec = importlib.util.spec_from_file_location("wave41_calendar_import_smoke", MODULE)
    assert spec is not None and spec.loader is not None
    imported = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(imported)
    assert issubclass(imported._CalendarPopup, imported.tk.Toplevel)
    assert issubclass(imported._CalendarRangePopup, imported.tk.Toplevel)
    assert callable(imported.pick_date_range)
    assert callable(imported.pick_date)

    module_text = MODULE.read_text(encoding="utf-8")
    mtree = ast.parse(module_text)
    lines = module_text.splitlines(keepends=True)
    found = {
        node.name: node for node in mtree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in TARGETS
    }
    assert list(name for name in TARGETS if name in found) == TARGETS
    assert len(found) == len(TARGETS)

    for name in TARGETS:
        node = found[name]
        source = "".join(lines[node.lineno - 1 : node.end_lineno])
        assert node.end_lineno - node.lineno + 1 == EXPECTED_LINES[name]
        assert hashlib.sha256(normalized(source).encode("utf-8")).hexdigest() == EXPECTED_SHA256[name]
        if isinstance(node, ast.ClassDef):
            actual_methods = [
                item.name for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            assert actual_methods == EXPECTED_METHODS[name], actual_methods

        for item in ast.walk(node):
            if isinstance(item, ast.Attribute):
                chain = ".".join(call_chain(item))
                assert not chain.startswith("self.db"), chain
            if isinstance(item, ast.Call):
                parts = call_chain(item.func)
                suffix = parts[-1].lower() if parts else ""
                assert suffix not in FORBIDDEN_CALL_SUFFIXES, ".".join(parts)
            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                upper = " ".join(item.value.upper().split())
                assert not any(token in upper for token in FORBIDDEN_SQL_TOKENS), upper

    desktop_text = DESKTOP.read_text(encoding="utf-8")
    dtree = ast.parse(desktop_text)
    originals = [
        node.name for node in dtree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in TARGETS
    ]
    assert not originals, originals
    assert "_configure_wave41_calendar(globals())" in desktop_text
    for name in TARGETS:
        assert f"{name} = _wave41{name}" in desktop_text
    assert desktop_text.count("pick_date(") >= 1
    print("Wave 41 calendar presentation regression passed:", EXPECTED_LINES, EXPECTED_SHA256)


if __name__ == "__main__":
    main()
