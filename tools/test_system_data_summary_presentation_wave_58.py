"""Exact-source regression for Wave 58 System Data summary helpers."""
from __future__ import annotations

import ast
import hashlib
import inspect
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
EXPECTED = {'_system_data_get_date': {'lines': 19, 'source_sha256': 'a6f3be4ac524d5375eb4520575cbdc0e853bb42b8ad74667d174a0b49316074d', 'dedented_sha256': '7e17d8e080f43814cc227820a4d5de4dadc829206b032d9b82befb4aab3dc850', 'signature': 'self', 'calls': ['_dt.strptime', 'messagebox.showerror', 'self._get_databank_focus_date', 'self.system_data_date_var.get', 'self.system_data_date_var.set', 'strftime', 'strip'], 'db_calls': []}, '_system_data_use_focus_date': {'lines': 8, 'source_sha256': '6c876f3607fc9b123f3be3f2af15a5157941c7208c36e2e339d0745dd134bb24', 'dedented_sha256': '4629723a11e6802f76f930b35d18c43230536ed55f874f9815e2ea4fae3e69de', 'signature': 'self', 'calls': ['_log_suppressed_once', 'self._get_databank_focus_date', 'self.system_data_date_var.set', 'strip'], 'db_calls': []}, '_system_data_refresh_summary': {'lines': 60, 'source_sha256': 'cc5a02d884b2c30fba6f5be3f8c1424fc4e66e1e4f2f250d96661dba421313c7', 'dedented_sha256': '2dc0fedf486fa30400327f333c0485e2220e34cce6aab21b2da9cfcbc7fd9dab', 'signature': 'self', 'calls': ['_fmt_amt', 'abs', 'bool', 'float', 'fmt_currency', 'hasattr', 'int', 'rec.get', 'round', 'self._system_data_get_date', 'self.db.get_databank_daily_total', 'self.db.get_databank_day_close', 'self.system_data_summary_var.set', 'strip'], 'db_calls': ['self.db.get_databank_daily_total', 'self.db.get_databank_day_close']}}
PROTECTED_MARKERS = ('.execute', '.executemany', '.commit', '.rollback', 'set_databank_day_close', 'replace_databank_day_collectors', 'delete_transactions_for_day', 'delete_transaction', 'add_or_update_transaction', 'close_day', 'reopen_day', 'backup', 'restore', 'password', 'print_databank_close_report', 'write_text', 'write_bytes', 'unlink')


def dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def main() -> None:
    import spina_app.system_data_summary_presentation as module

    assert module.SYSTEM_DATA_SUMMARY_PRESENTATION_METHODS == EXPECTED
    app_text = APP.read_text(encoding="utf-8-sig")
    app_tree = ast.parse(app_text, filename=str(APP))
    app_class = next(node for node in app_tree.body if isinstance(node, ast.ClassDef) and node.name == "App")
    remaining = {child.name for child in app_class.body if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))}

    for name, expected in EXPECTED.items():
        assert name not in remaining
        function = getattr(module, name)
        source = inspect.getsource(function)
        assert len(source.splitlines()) == expected["lines"]
        assert hashlib.sha256(source.encode("utf-8")).hexdigest() == expected["dedented_sha256"]
        node = ast.parse(source).body[0]
        assert ast.unparse(node.args) == expected["signature"]
        calls = sorted({dotted(call.func) for call in ast.walk(node) if isinstance(call, ast.Call) and dotted(call.func)})
        assert calls == expected["calls"]
        assert [call for call in calls if call.startswith("self.db.")] == expected["db_calls"]
        lowered = "\n".join(calls).lower()
        assert not [marker for marker in PROTECTED_MARKERS if marker in lowered]

    assert app_text.count("_configure_wave58_system_data_summary(globals())") == 1
    for name in EXPECTED:
        assert app_text.count(f"App.{name} = _wave58{name}") == 1
    print("Wave 58 exact System Data summary extraction regression passed")


if __name__ == "__main__":
    main()
