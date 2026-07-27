# Wave 62 Delete Day boundary plan

Wave 62 analyzes the complete Data Bank Delete Day dialog before any extraction.

- Base merge: `45d781b2d23bb1e2772cf8d5cd3a35e4f8154d65`
- Target: `App.open_delete_day_dialog`
- Lines: **141** (9938–10078)
- Signature: `self`
- Source SHA-256: `b41b22e7c18f2e7f391f4cd400a9f0034c9ca535d2c7b10a9045db35af3d0407`
- Dedented SHA-256: `1947e0359e0dd97f49e90ac8fe3e3a9357a67213363416908d206b381ee076c0`
- Risk class: **authentication / backup / destructive database write**

## Database and sensitive calls

- Database calls: `["self.db.conn.cursor", "self.db.delete_transactions_for_day", "self.db.get_databank_day_close"]`
- Sensitive calls: `["cur.execute", "messagebox.askyesno", "messagebox.showerror", "messagebox.showinfo", "self._prompt_current_password", "self.db.delete_transactions_for_day", "self.refresh_audit_tab", "self.refresh_data_grid", "self.refresh_reports", "simpledialog.askstring"]`

## Nested functions

- None

## Required extraction gates

- Exact source, signature, call-set, database-call, and string preservation
- Fake-database tests for successful deletion, cancellation, wrong password, backup failure, and DB failure
- Real Tkinter dialog construction and button-flow test
- Exact preservation of Wave 61 cell-write bindings
- Protected import, Daily Close, audit, reports, backups, and Collector Route regressions
- Permanent architecture map and repository audits
- Exact-head Windows validation and desktop testing before merge

## Raw analyzer report

```json
{
  "base_merge": "45d781b2d23bb1e2772cf8d5cd3a35e4f8154d65",
  "target": "open_delete_day_dialog",
  "start_line": 9938,
  "end_line": 10078,
  "lines": 141,
  "signature": "self",
  "source_sha256": "b41b22e7c18f2e7f391f4cd400a9f0034c9ca535d2c7b10a9045db35af3d0407",
  "dedented_sha256": "1947e0359e0dd97f49e90ac8fe3e3a9357a67213363416908d206b381ee076c0",
  "calls": [
    "_date",
    "_date.today",
    "_dt.strptime",
    "_json.load",
    "_log.items",
    "_os.path.exists",
    "_v.get",
    "bool",
    "cur.execute",
    "data_path",
    "fetchone",
    "float",
    "fmt_currency",
    "get",
    "getattr",
    "globals",
    "int",
    "isinstance",
    "list",
    "messagebox.askyesno",
    "messagebox.showerror",
    "messagebox.showinfo",
    "open",
    "self._prompt_current_password",
    "self.db.conn.cursor",
    "self.db.delete_transactions_for_day",
    "self.db.get_databank_day_close",
    "self.refresh_audit_tab",
    "self.refresh_data_grid",
    "self.refresh_reports",
    "simpledialog.askstring",
    "split",
    "str",
    "strftime",
    "strip"
  ],
  "db_calls": [
    "self.db.conn.cursor",
    "self.db.delete_transactions_for_day",
    "self.db.get_databank_day_close"
  ],
  "sensitive_calls": [
    "cur.execute",
    "messagebox.askyesno",
    "messagebox.showerror",
    "messagebox.showinfo",
    "self._prompt_current_password",
    "self.db.delete_transactions_for_day",
    "self.refresh_audit_tab",
    "self.refresh_data_grid",
    "self.refresh_reports",
    "simpledialog.askstring"
  ],
  "nested_functions": [],
  "strings": [
    "%Y-%m-%d",
    ".",
    "Backup saved here:",
    "Confirm Delete a Day",
    "DELETE DATA BANK DAY:",
    "Data Bank transaction row(s) for",
    "Delete a Day",
    "Delete all Data Bank entries for one selected date, with backup + password confirmation.",
    "Deleted",
    "Encoder import-log cleared:",
    "Encoder import-log entries to clear:",
    "Enter the date to delete from Data Bank (YYYY-MM-DD):\n\nThis deletes BOTH Regular and 7x7 payments/missed-payment rows for that date.",
    "Enter your current account password to delete this day.",
    "Failed to delete day:",
    "Invalid date. Use YYYY-MM-DD.",
    "No Data Bank entries or import-log markers found for",
    "SELECT COUNT(*), COALESCE(SUM(COALESCE(payment,0)),0) FROM transactions WHERE date(date)=date(?)",
    "This will:\n  \u2022 create a backup file first\n  \u2022 delete all Regular and 7x7 entries for this date\n  \u2022 clear/reopen the Daily Close record for this date\n  \u2022 clear encoder import markers for this date so you can re-import\n\nContinue?",
    "Total payment amount affected:",
    "Transaction rows to delete:",
    "_dbank_last_day",
    "backup_path",
    "databank:delete_day_button",
    "date",
    "deleted",
    "encoder_import_log.json",
    "entr(y/ies).",
    "fmt_currency",
    "import_log_cleared",
    "r",
    "user_name",
    "utf-8",
    "|"
  ],
  "protected_wave61_bindings": [
    "App._save_cell_edit = _wave61_save_cell_edit",
    "App.delete_selected_cell = _wave61_delete_selected_cell",
    "App._mark_missed_for_selected = _wave61_mark_missed_for_selected"
  ]
}
```
