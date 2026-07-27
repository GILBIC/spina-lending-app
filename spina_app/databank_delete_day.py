"""Data Bank Delete Day destructive workflow with a fail-closed password gate."""
from __future__ import annotations

_DATABANK_DELETE_DAY_DEPENDENCIES = {}
_PROTECTED_GLOBALS = {
    "_DATABANK_DELETE_DAY_DEPENDENCIES", "_PROTECTED_GLOBALS",
    "configure_databank_delete_day_dependencies", "open_delete_day_dialog",
    "DATABANK_DELETE_DAY_METHOD",
}


def configure_databank_delete_day_dependencies(namespace):
    _DATABANK_DELETE_DAY_DEPENDENCIES.clear()
    _DATABANK_DELETE_DAY_DEPENDENCIES.update(namespace)
    for name, value in namespace.items():
        if name not in _PROTECTED_GLOBALS:
            globals()[name] = value


DATABANK_DELETE_DAY_METHOD = {'calls': ['_date',
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
 'db_calls': ['self.db.conn.cursor',
              'self.db.delete_transactions_for_day',
              'self.db.get_databank_day_close'],
 'dedented_sha256': '9ecf5c06ba88ed6dcb44da83aca2cd8458b968ca110a9a48ba5f2faf7a3a8511',
 'lines': 142,
 'signature': 'self',
 'source_sha256': '9ecf5c06ba88ed6dcb44da83aca2cd8458b968ca110a9a48ba5f2faf7a3a8511',
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
             'Delete all Data Bank entries for one selected date, with backup + password '
             'confirmation.',
             'Deleted ',
             'Enter the date to delete from Data Bank (YYYY-MM-DD):\n'
             '\n'
             'This deletes BOTH Regular and 7x7 payments/missed-payment rows for that date.',
             'Enter your current account password to delete this day.',
             'Failed to delete day:\n',
             'Invalid date. Use YYYY-MM-DD.',
             'No Data Bank entries or import-log markers found for ',
             'Password verification failed:\n',
             'SELECT COUNT(*), COALESCE(SUM(COALESCE(payment,0)),0) FROM transactions WHERE '
             'date(date)=date(?)',
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


def open_delete_day_dialog(self):
    """Delete all Data Bank entries for one selected date, with backup + password confirmation."""
    from tkinter import messagebox, simpledialog
    from datetime import date as _date, datetime as _dt

    # Default date: last clicked Data Bank day cell, otherwise today.
    default_date = _date.today().strftime("%Y-%m-%d")
    try:
        day = getattr(self, "_dbank_last_day", None)
        if day:
            default_date = _date(int(self.grid_year), int(self.grid_month), int(day)).strftime("%Y-%m-%d")
    except Exception:
        default_date = _date.today().strftime("%Y-%m-%d")

    ds = simpledialog.askstring(
        "Delete a Day",
        "Enter the date to delete from Data Bank (YYYY-MM-DD):\n\n"
        "This deletes BOTH Regular and 7x7 payments/missed-payment rows for that date.",
        initialvalue=default_date,
        parent=self.root,
    )
    if ds is None:
        return
    ds = str(ds or "").strip()[:10]
    try:
        ds = _dt.strptime(ds, "%Y-%m-%d").strftime("%Y-%m-%d")
    except Exception:
        messagebox.showerror("Delete a Day", "Invalid date. Use YYYY-MM-DD.")
        return

    # Count affected rows before asking final confirmation.
    count = 0
    total = 0.0
    close_exists = False
    import_log_count = 0
    try:
        cur = self.db.conn.cursor()
        row = cur.execute(
            "SELECT COUNT(*), COALESCE(SUM(COALESCE(payment,0)),0) FROM transactions WHERE date(date)=date(?)",
            (ds,),
        ).fetchone()
        if row:
            count = int(row[0] or 0)
            total = float(row[1] or 0.0)
        close_exists = bool(self.db.get_databank_day_close(ds, loan_type=None))
    except Exception:
        count = 0
        total = 0.0
        close_exists = False

    # Count encoder import-log entries too. This lets Delete Day clear stale
    # import markers even if transaction rows were already removed manually.
    try:
        import json as _json
        import os as _os
        log_path = data_path("encoder_import_log.json")
        if log_path and _os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8") as f:
                _log = _json.load(f) or {}
            if isinstance(_log, dict):
                for _k, _v in list(_log.items()):
                    _hit = False
                    try:
                        if isinstance(_v, dict) and str(_v.get("date") or "").strip()[:10] == ds:
                            _hit = True
                    except Exception:
                        _hit = False
                    try:
                        if not _hit and str(_k or "").split("|", 1)[0] == ds:
                            _hit = True
                    except Exception:
                        pass
                    if _hit:
                        import_log_count += 1
    except Exception:
        import_log_count = 0

    if count <= 0 and not close_exists and import_log_count <= 0:
        messagebox.showinfo("Delete a Day", f"No Data Bank entries or import-log markers found for {ds}.")
        return

    msg = (
        f"DELETE DATA BANK DAY: {ds}\n\n"
        f"Transaction rows to delete: {count}\n"
        f"Total payment amount affected: {fmt_currency(total) if 'fmt_currency' in globals() else total}\n"
        f"Encoder import-log entries to clear: {import_log_count}\n\n"
        "This will:\n"
        "  • create a backup file first\n"
        "  • delete all Regular and 7x7 entries for this date\n"
        "  • clear/reopen the Daily Close record for this date\n"
        "  • clear encoder import markers for this date so you can re-import\n\n"
        "Continue?"
    )
    if not messagebox.askyesno("Confirm Delete a Day", msg, parent=self.root):
        return

    # Password gate, same style as Daily Close.
    try:
        ok = self._prompt_current_password(
            title="Delete a Day",
            prompt="Enter your current account password to delete this day."
        )
    except Exception as exc:
        messagebox.showerror("Delete a Day", f"Password verification failed:\n{exc}")
        return
    if not ok:
        return

    try:
        result = self.db.delete_transactions_for_day(
            ds,
            changed_by=(getattr(self, "user_name", "") or "").strip(),
            source="databank:delete_day_button",
            reset_close=True,
        )
    except Exception as e:
        messagebox.showerror("Delete a Day", f"Failed to delete day:\n{e}")
        return

    # Refresh relevant UI.
    try:
        self.refresh_data_grid()
    except Exception:
        pass
    try:
        self.refresh_reports()
    except Exception:
        pass
    try:
        self.refresh_audit_tab()
    except Exception:
        pass

    deleted = int((result or {}).get("deleted") or 0)
    import_log_cleared = int((result or {}).get("import_log_cleared") or 0)
    backup_path = (result or {}).get("backup_path") or ""
    extra = ""
    if import_log_cleared:
        extra += f"\nEncoder import-log cleared: {import_log_cleared} entr(y/ies)."
    if backup_path:
        extra += f"\n\nBackup saved here:\n{backup_path}"
    messagebox.showinfo("Delete a Day", f"Deleted {deleted} Data Bank transaction row(s) for {ds}.{extra}")
