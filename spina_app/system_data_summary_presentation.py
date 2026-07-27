"""System Data date and summary helpers extracted in Wave 58."""
from __future__ import annotations

_SYSTEM_DATA_SUMMARY_DEPENDENCIES = {}
_PROTECTED_GLOBALS = {'SYSTEM_DATA_SUMMARY_PRESENTATION_METHODS', '__spec__', '__cached__', '_system_data_get_date', 'configure_system_data_summary_dependencies', '__file__', '__builtins__', '__loader__', '_system_data_use_focus_date', '__package__', '_PROTECTED_GLOBALS', '__name__', '_SYSTEM_DATA_SUMMARY_DEPENDENCIES', '__doc__', '_system_data_refresh_summary'}

def configure_system_data_summary_dependencies(namespace):
    _SYSTEM_DATA_SUMMARY_DEPENDENCIES.clear()
    _SYSTEM_DATA_SUMMARY_DEPENDENCIES.update(namespace)
    for name, value in namespace.items():
        if name not in _PROTECTED_GLOBALS:
            globals()[name] = value

SYSTEM_DATA_SUMMARY_PRESENTATION_METHODS = {'_system_data_get_date': {'lines': 19, 'source_sha256': 'a6f3be4ac524d5375eb4520575cbdc0e853bb42b8ad74667d174a0b49316074d', 'dedented_sha256': '7e17d8e080f43814cc227820a4d5de4dadc829206b032d9b82befb4aab3dc850', 'signature': 'self', 'calls': ['_dt.strptime', 'messagebox.showerror', 'self._get_databank_focus_date', 'self.system_data_date_var.get', 'self.system_data_date_var.set', 'strftime', 'strip'], 'db_calls': []}, '_system_data_use_focus_date': {'lines': 8, 'source_sha256': '6c876f3607fc9b123f3be3f2af15a5157941c7208c36e2e339d0745dd134bb24', 'dedented_sha256': '4629723a11e6802f76f930b35d18c43230536ed55f874f9815e2ea4fae3e69de', 'signature': 'self', 'calls': ['_log_suppressed_once', 'self._get_databank_focus_date', 'self.system_data_date_var.set', 'strip'], 'db_calls': []}, '_system_data_refresh_summary': {'lines': 60, 'source_sha256': 'cc5a02d884b2c30fba6f5be3f8c1424fc4e66e1e4f2f250d96661dba421313c7', 'dedented_sha256': '2dc0fedf486fa30400327f333c0485e2220e34cce6aab21b2da9cfcbc7fd9dab', 'signature': 'self', 'calls': ['_fmt_amt', 'abs', 'bool', 'float', 'fmt_currency', 'hasattr', 'int', 'rec.get', 'round', 'self._system_data_get_date', 'self.db.get_databank_daily_total', 'self.db.get_databank_day_close', 'self.system_data_summary_var.set', 'strip'], 'db_calls': ['self.db.get_databank_daily_total', 'self.db.get_databank_day_close']}}

def _system_data_get_date(self):
    from datetime import datetime as _dt
    from tkinter import messagebox
    ds = ''
    try:
        ds = (self.system_data_date_var.get() or '').strip()
    except Exception:
        ds = ''
    if not ds:
        ds = (self._get_databank_focus_date() or '').strip()
        try:
            self.system_data_date_var.set(ds)
        except Exception:
            pass
    try:
        return _dt.strptime(ds, '%Y-%m-%d').strftime('%Y-%m-%d')
    except Exception:
        messagebox.showerror('Data', 'Use date format YYYY-MM-DD.')
        return ''

def _system_data_use_focus_date(self):
    try:
        ds = (self._get_databank_focus_date() or '').strip()
        if ds:
            self.system_data_date_var.set(ds)
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_system_data_focus_date', 'suppressed exception excpass_system_data_focus_date', __spina_exc)
        pass

def _system_data_refresh_summary(self):
    ds = self._system_data_get_date()
    if not ds:
        return

    def _fmt_amt(v):
        try:
            return fmt_currency(v)
        except Exception:
            try:
                return f"{float(v or 0.0):,.2f}"
            except Exception:
                return '0.00'

    try:
        reg_expected = round(float(self.db.get_databank_daily_total(ds, loan_type='Regular') or 0.0), 2)
    except Exception:
        reg_expected = 0.0
    try:
        x7_expected = round(float(self.db.get_databank_daily_total(ds, loan_type='7x7') or 0.0), 2)
    except Exception:
        x7_expected = 0.0

    rec = None
    try:
        rec = self.db.get_databank_day_close(ds) if hasattr(self, 'db') else None
    except Exception:
        rec = None

    if rec:
        expected = round(float(rec.get('expected_amount') or 0.0), 2)
        actual = round(float(rec.get('actual_cash') or 0.0), 2)
        variance = round(float(rec.get('variance') or 0.0), 2)
        variance_status = (rec.get('variance_status') or 'Balanced').strip()
        workflow = (rec.get('variance_workflow_status') or rec.get('workflow_status') or 'Open').strip()
        closed_txt = 'Closed' if bool(int(rec.get('is_closed') or 0)) else 'Open'
        note = (rec.get('note') or '').strip()
        note_txt = f"\nNote: {note}" if note else ''
        txt = (
            f"Date: {ds}\n"
            f"Regular Expected: {_fmt_amt(reg_expected)}\n"
            f"7x7 Expected: {_fmt_amt(x7_expected)}\n"
            f"Total Expected: {_fmt_amt(expected)}\n"
            f"Actual Cash: {_fmt_amt(actual)}\n"
            f"Variance: {_fmt_amt(abs(variance))} ({variance_status})\n"
            f"Workflow: {workflow} | Status: {closed_txt}{note_txt}"
        )
    else:
        combined = round(reg_expected + x7_expected, 2)
        txt = (
            f"Date: {ds}\n"
            f"Regular Expected: {_fmt_amt(reg_expected)}\n"
            f"7x7 Expected: {_fmt_amt(x7_expected)}\n"
            f"Total Expected: {_fmt_amt(combined)}\n"
            f"No Daily Close record yet for this date."
        )
    try:
        self.system_data_summary_var.set(txt)
    except Exception:
        pass
