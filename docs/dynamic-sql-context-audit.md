# Dynamic SQL Context Audit

This is a read-only audit for dynamic SQL execution sites in the SPINA desktop app.

## Purpose

The quality audit can count possible dynamic SQL calls, but it does not always show enough surrounding code to decide whether a change is safe. This tool reports context for `execute`, `executemany`, and `executescript` calls where the SQL argument is not a plain string literal.

## Safety rules

- The tool does not edit the app source.
- Treat payment, balance, 7x7, report, collector, backup, restore, migration, and database paths as protected review-only areas.
- Do not replace SQL dynamically unless the exact table/column family is manually confirmed.
- Prefer explicit whitelists for table or column names when a future change is approved.

## Local use

From the repository root:

```bat
python tools\audit_dynamic_sql_context.py --json dynamic-sql-context-report.json
```

Upload `dynamic-sql-context-report.json` before any cleanup is attempted.

## Expected workflow

1. Run the audit.
2. Review non-protected dynamic SQL separately from protected database/payment/report logic.
3. Change only one approved SQL family at a time.
4. Run:

```bat
python -m py_compile "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
```

5. Smoke-test SPINA, especially login, clients, payments, reports, backups, and collector routes.
