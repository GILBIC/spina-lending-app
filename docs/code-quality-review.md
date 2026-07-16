# SPINA code-quality review

Reviewed target: `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py`

## Safe fixes included in this review

### 1. Background tasks could run twice after an error

`_run_long_task()` inspected a callback signature and invoked the callback inside the same broad `try` block. When the callback itself raised an exception, the `except` block called it again as a fallback. A failed Excel import, backup, report, or database task could therefore repeat writes or repeat expensive work.

The callback is now invoked exactly once. Only signature-inspection failure falls back to a no-argument call; task exceptions propagate to the worker error handler.

### 2. Password changes could report success when saving failed

`_save_users_db()` swallowed write failures and returned no status. `_set_user_password()` always returned `True` after calling it, so the password dialog could say the password was changed even when disk or permission errors prevented the write.

Account saves now return `True` or `False`, and password updates report success only after an actual successful atomic save.

### 3. A damaged `users.json` could be silently replaced

The account loader treated every read error as an empty first-run file. A malformed, locked, or temporarily unreadable account file could be replaced with default accounts.

Successful saves now maintain `data/users.json.bak`. The loader distinguishes a genuinely missing file from a damaged/unreadable file, restores a valid backup when possible, and leaves both files untouched when neither can be read.

### 4. Performance indexes were checked repeatedly

The large-data refresh helpers called ten `CREATE INDEX IF NOT EXISTS` statements and committed on repeated Clients/Data Bank refreshes. The module also constructed an extra `LoanDB` object at startup solely to run the same index setup, causing another connection and schema pass.

Index setup is now guarded to run once per application process and uses the real application database connection on the first optimized refresh. The extra module-load database connection was removed.

## Automated review added

`tools/quality_audit.py` reports:

- broad and swallowed exception handlers
- bare `except` blocks
- database connection, `commit()`, `fetchall()`, and Excel-load call counts
- very large or branch-heavy functions
- hard-coded default-account password literals
- critical patterns such as retrying a failed task callback or opening `LoanDB` at module load

`tools/test_quality_fixes.py` prevents the four fixed patterns from returning.

## Remaining risks and recommended order

1. **Financial calculation tests:** add fixed examples for Regular and 7x7 interest/principal allocation, renewals, ADV/PASS, balances, and due dates before deeper refactoring.
2. **Known default passwords:** replace public defaults with a first-run owner setup or randomly generated one-time credential.
3. **Exception handling:** the file contains thousands of broad exception handlers and hundreds that silently pass. Replace them feature-by-feature with logged, specific failures.
4. **Very large functions:** ledger/collector printing and collector selection contain thousands of lines. Split calculation, query, layout, and file-writing stages after tests exist.
5. **Patch-layer architecture:** flatten repeated `App.__init__`, dashboard, collector, client, and theme monkey patches into explicit methods.
6. **PostgreSQL compatibility layer:** gradually replace regex-translated SQLite SQL with native parameterized PostgreSQL queries for critical payment and report paths.
7. **Authentication storage:** move multi-PC staff accounts away from local `users.json` when centralized account access is required.
8. **File storage memory:** PDF and image storage currently reads complete files into memory. Stream or limit large files if report/image size grows.

## Required desktop checks before merge

- Owner/staff login and password change
- Restart after changing a password
- Dashboard and Clients loading
- Data Bank month loading and payment entry
- Excel import error handling
- Backup/history tools
- Reports, Full Daily Ledger, and Collector Route PDF
- Regular and 7x7 balances
