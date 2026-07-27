from __future__ import annotations

import ast
import hashlib
import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE_PATH = ROOT / "spina_app" / "system_data_presentation.py"
TARGETS = ('_show_system_data_tab', '_hide_system_data_tab', '_system_data_get_date', '_system_data_use_focus_date', '_system_data_refresh_summary', '_system_data_open_close', '_system_data_open_history', '_system_data_open_records', '_system_data_print_report', '_build_system_data_tab')
EXPECTED = {'_show_system_data_tab': {'lines': 10,
                           'sha256': '97518f51463e32f6b7222e505629edb860b144273485d3416e78cbf606b973ee',
                           'signature': 'self',
                           'calls': ['_log_suppressed_once', 'self.nb.add', 'self.nb.tab', 'self.nb.tabs', 'set', 'str']},
 '_hide_system_data_tab': {'lines': 6,
                           'sha256': '2cc94304e83ecae87891240bd36de8d2762137639004abd3a27be55200dd40f8',
                           'signature': 'self',
                           'calls': ['_log_suppressed_once', 'self.nb.hide']},
 '_system_data_get_date': {'lines': 19,
                           'sha256': 'f22b289a8087cb71d41add83764f8f8be19b78bf880c2b48f70fc1f5d8aaadc9',
                           'signature': 'self',
                           'calls': ['_dt.strptime',
                                     'messagebox.showerror',
                                     'self._get_databank_focus_date',
                                     'self.system_data_date_var.get',
                                     'self.system_data_date_var.set',
                                     'strftime',
                                     'strip']},
 '_system_data_use_focus_date': {'lines': 8,
                                 'sha256': '9901deaa24a7cefc43e532d31afb65e481c52ba08c09d4ea433836606ab1858d',
                                 'signature': 'self',
                                 'calls': ['_log_suppressed_once', 'self._get_databank_focus_date', 'self.system_data_date_var.set', 'strip']},
 '_system_data_refresh_summary': {'lines': 60,
                                  'sha256': 'c6d42e2c651689494e4bded48d8754fdb8ee3ec1a9ecb85053819cea8cf7bcf6',
                                  'signature': 'self',
                                  'calls': ['_fmt_amt',
                                            'abs',
                                            'bool',
                                            'float',
                                            'fmt_currency',
                                            'hasattr',
                                            'int',
                                            'rec.get',
                                            'round',
                                            'self._system_data_get_date',
                                            'self.db.get_databank_daily_total',
                                            'self.db.get_databank_day_close',
                                            'self.system_data_summary_var.set',
                                            'strip']},
 '_system_data_open_close': {'lines': 11,
                             'sha256': 'c2a29a0b52164e57da672c065b5b983b7c81614b1f7f3114c768fe1fb85386e4',
                             'signature': 'self',
                             'calls': ['self._system_data_get_date', 'self._system_data_refresh_summary', 'self.open_databank_close_dialog']},
 '_system_data_open_history': {'lines': 5,
                               'sha256': '7deeb5e16c62824a50a62d186c5d80ee91fddc1494e5d417c75275ad0a94a4b4',
                               'signature': 'self',
                               'calls': ['self._system_data_get_date', 'self.open_databank_close_history_dialog']},
 '_system_data_open_records': {'lines': 5,
                               'sha256': '45c4ff9858104858fbe90f39a08fa5021aed8585f64f22b88680aaee717627ee',
                               'signature': 'self',
                               'calls': ['self._system_data_get_date', 'self.open_databank_close_records_dialog']},
 '_system_data_print_report': {'lines': 5,
                               'sha256': '1dd96e2737cca13fc2ae47a87536f62a23c417dc51174abf711cdb6e95341b3f',
                               'signature': 'self',
                               'calls': ['self._system_data_get_date', 'self.print_databank_close_report']},
 '_build_system_data_tab': {'lines': 46,
                            'sha256': 'a2b2a3727daf45822c8186a3262c6302a2ced138b68c01dcfee6fedd4ca4d30f',
                            'signature': 'self',
                            'calls': ['_dt.now',
                                      '_log_suppressed_once',
                                      'controls.columnconfigure',
                                      'controls.grid',
                                      'grid',
                                      'outer.columnconfigure',
                                      'outer.rowconfigure',
                                      'range',
                                      'self._get_databank_focus_date',
                                      'self._system_data_refresh_summary',
                                      'strftime',
                                      'summary.columnconfigure',
                                      'summary.grid',
                                      'summary.rowconfigure',
                                      'title.columnconfigure',
                                      'title.grid',
                                      'tk.StringVar',
                                      'ttk.Button',
                                      'ttk.Entry',
                                      'ttk.Frame',
                                      'ttk.Label',
                                      'ttk.LabelFrame']}}
WRITE_MARKERS = {'set_transaction', 'reopen_day', 'unlink', 'mkdir', 'rename', 'renew_client', 'commit', 'executemany', 'execute', 'save_transaction', 'archive_client', 'write_bytes', 'save_settings', 'rollback', 'remove', 'add_client', 'close_day', 'replace', 'write_text', 'update_client', 'run_write', 'delete_client'}


def normalized(source: str) -> str:
    return "\n".join(line.rstrip() for line in source.strip().splitlines())


def source_hash(source: str) -> str:
    return hashlib.sha256(normalized(source).encode("utf-8")).hexdigest()


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def main() -> None:
    module = importlib.import_module("spina_app.system_data_presentation")
    assert module.SYSTEM_DATA_PRESENTATION_TARGETS == list(TARGETS)
    assert module.SYSTEM_DATA_PRESENTATION_TOTAL_SOURCE_LINES == 175
    assert module.SYSTEM_DATA_PRESENTATION_SOURCE_LINES == {name: item["lines"] for name, item in EXPECTED.items()}
    assert module.SYSTEM_DATA_PRESENTATION_SOURCE_SHA256 == {name: item["sha256"] for name, item in EXPECTED.items()}
    assert module.SYSTEM_DATA_PRESENTATION_SIGNATURES == {name: item["signature"] for name, item in EXPECTED.items()}
    assert module.SYSTEM_DATA_PRESENTATION_CALLS == {name: item["calls"] for name, item in EXPECTED.items()}

    module_text = MODULE_PATH.read_text(encoding="utf-8")
    module_lines = module_text.splitlines()
    module_tree = ast.parse(module_text)
    for name in TARGETS:
        matches = [node for node in module_tree.body if isinstance(node, ast.FunctionDef) and node.name == name]
        assert len(matches) == 1, (name, len(matches))
        node = matches[0]
        source = "\n".join(module_lines[node.lineno - 1 : node.end_lineno])
        assert len(normalized(source).splitlines()) == EXPECTED[name]["lines"]
        assert source_hash(source) == EXPECTED[name]["sha256"]
        assert ast.unparse(node.args) == EXPECTED[name]["signature"]
        calls = sorted({dotted(call.func) for call in ast.walk(node) if isinstance(call, ast.Call) and dotted(call.func)})
        assert calls == EXPECTED[name]["calls"], (name, calls)
        write_like = sorted({call for call in calls if call.rsplit(".", 1)[-1].lower() in WRITE_MARKERS})
        assert not write_like, (name, write_like)

    desktop_text = DESKTOP.read_text(encoding="utf-8")
    desktop_tree = ast.parse(desktop_text)
    app = next(node for node in desktop_tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    remaining = {node.name for node in app.body if isinstance(node, ast.FunctionDef)}
    assert not (set(TARGETS) & remaining), sorted(set(TARGETS) & remaining)

    imports = [
        node for node in desktop_tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "spina_app.system_data_presentation"
    ]
    assert len(imports) == 1
    aliases = {(item.name, item.asname) for item in imports[0].names}
    assert ("configure_system_data_presentation_dependencies", "_wave55_configure_system_data_presentation_dependencies") in aliases
    for name in TARGETS:
        assert (name, "_wave55" + name) in aliases

    configure = [
        node for node in desktop_tree.body
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "_wave55_configure_system_data_presentation_dependencies"
    ]
    assert len(configure) == 1

    bindings = []
    for node in desktop_tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if (
            isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name)
            and target.value.id == "App" and target.attr in TARGETS
            and isinstance(node.value, ast.Name)
        ):
            bindings.append((target.attr, node.value.id, node.lineno))
    assert sorted((name, value) for name, value, _ in bindings) == sorted((name, "_wave55" + name) for name in TARGETS)
    assert all(app.end_lineno < line for _, _, line in bindings)

    print("Wave 55 System Data presentation regression passed.")


if __name__ == "__main__":
    main()
