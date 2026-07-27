"""Permanent exact-source regression for Wave 62 Delete Day."""
from __future__ import annotations

import ast
import hashlib
import importlib
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
MODULE_PATH = ROOT / "spina_app" / "databank_delete_day.py"
EXPECTED = {'calls': ['_date',
           '_date.today',
           '_dt.strptime',
           '_json.load',
           '_log.items',
           '_os.path.exists',
           '_v.get',
           'bool',
           'cur.execute',
           'data_path',
           'fetchone',
           'float',
           'fmt_currency',
           'get',
           'getattr',
           'globals',
           'int',
           'isinstance',
           'list',
           'messagebox.askyesno',
           'messagebox.showerror',
           'messagebox.showinfo',
           'open',
           'self._prompt_current_password',
           'self.db.conn.cursor',
           'self.db.delete_transactions_for_day',
           'self.db.get_databank_day_close',
           'self.refresh_audit_tab',
           'self.refresh_data_grid',
           'self.refresh_reports',
           'simpledialog.askstring',
           'split',
           'str',
           'strftime',
           'strip'],
 'db_calls': ['self.db.conn.cursor', 'self.db.delete_transactions_for_day', 'self.db.get_databank_day_close'],
 'dedented_sha256': '1947e0359e0dd97f49e90ac8fe3e3a9357a67213363416908d206b381ee076c0',
 'lines': 141,
 'signature': 'self',
 'source_sha256': 'b41b22e7c18f2e7f391f4cd400a9f0034c9ca535d2c7b10a9045db35af3d0407',
 'strings': ['',
             '\n\nBackup saved here:\n',
             '\n'
             '\n'
             'This will:\n'
             '  • create a backup file first\n'
             '  • delete all Regular and 7x7 entries for this date\n'
             '  • clear/reopen the Daily Close record for this date\n'
             '  • clear encoder import markers for this date so you can re-import\n'
             '\n'
             'Continue?',
             '\n\nTransaction rows to delete: ',
             '\nEncoder import-log cleared: ',
             '\nEncoder import-log entries to clear: ',
             '\nTotal payment amount affected: ',
             ' Data Bank transaction row(s) for ',
             ' entr(y/ies).',
             '%Y-%m-%d',
             '.',
             'Confirm Delete a Day',
             'DELETE DATA BANK DAY: ',
             'Delete a Day',
             'Delete all Data Bank entries for one selected date, with backup + password confirmation.',
             'Deleted ',
             'Enter the date to delete from Data Bank (YYYY-MM-DD):\n'
             '\n'
             'This deletes BOTH Regular and 7x7 payments/missed-payment rows for that date.',
             'Enter your current account password to delete this day.',
             'Failed to delete day:\n',
             'Invalid date. Use YYYY-MM-DD.',
             'No Data Bank entries or import-log markers found for ',
             'SELECT COUNT(*), COALESCE(SUM(COALESCE(payment,0)),0) FROM transactions WHERE date(date)=date(?)',
             '_dbank_last_day',
             'backup_path',
             'databank:delete_day_button',
             'date',
             'deleted',
             'encoder_import_log.json',
             'fmt_currency',
             'import_log_cleared',
             'r',
             'user_name',
             'utf-8',
             '|']}
PROTECTED_WAVE61 = ['App._save_cell_edit = _wave61_save_cell_edit', 'App.delete_selected_cell = _wave61_delete_selected_cell', 'App._mark_missed_for_selected = _wave61_mark_missed_for_selected']


def sha(source: str) -> str:
    return hashlib.sha256(source.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def dotted(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return None


def main() -> None:
    module_text = MODULE_PATH.read_text(encoding="utf-8")
    module_lines = module_text.splitlines(keepends=True)
    module_tree = ast.parse(module_text)
    functions = {node.name: node for node in module_tree.body if isinstance(node, ast.FunctionDef)}
    node = functions["open_delete_day_dialog"]
    source = "".join(module_lines[node.lineno - 1:node.end_lineno])
    calls = sorted({
        value for child in ast.walk(node)
        if isinstance(child, ast.Call)
        for value in [dotted(child.func)]
        if value
    })
    strings = sorted({
        child.value for child in ast.walk(node)
        if isinstance(child, ast.Constant) and isinstance(child.value, str)
    })
    imported = importlib.import_module("spina_app.databank_delete_day")
    assert imported.DATABANK_DELETE_DAY_METHOD == EXPECTED
    assert node.end_lineno - node.lineno + 1 == EXPECTED["lines"]
    assert sha(textwrap.dedent(source)) == EXPECTED["dedented_sha256"]
    assert ast.unparse(node.args) == EXPECTED["signature"]
    assert calls == EXPECTED["calls"]
    assert sorted(call for call in calls if call.startswith("self.db.")) == EXPECTED["db_calls"]
    assert strings == EXPECTED["strings"]

    app_text = APP_PATH.read_text(encoding="utf-8")
    app_tree = ast.parse(app_text)
    app_class = next(node for node in app_tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    app_methods = {node.name for node in app_class.body if isinstance(node, ast.FunctionDef)}
    assert "open_delete_day_dialog" not in app_methods
    assert app_text.count("configure_databank_delete_day_dependencies as _configure_wave62_databank_delete_day") == 1
    assert app_text.count("App.open_delete_day_dialog = _wave62_open_delete_day_dialog") == 1
    for marker in PROTECTED_WAVE61:
        assert app_text.count(marker) == 1
    print("Wave 62 exact Delete Day regression passed:", EXPECTED["lines"], "lines")


if __name__ == "__main__":
    main()
