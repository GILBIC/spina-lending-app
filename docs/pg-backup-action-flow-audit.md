# PostgreSQL backup action flow audit

This read-only audit checks the outer UI action flow for PostgreSQL backup, verify backup, and restore-test actions.

## Why this exists

The blocking UI audits found `subprocess.run` calls around PostgreSQL command-line tools. The context and caller reports showed those helpers are protected backup/database code, so the next safe step is to inspect whether the outer UI button handlers already route the heavy work through the app's existing `_run_long_task` worker path.

## Local command

```bat
python tools\audit_pg_backup_action_flow.py --json pg-backup-action-flow-report.json
```

Upload the JSON report before any app-source cleanup is attempted.

## Safety rules

- This tool only reads source.
- It does not edit the main app.
- Treat backup, restore, PostgreSQL, and database code as protected review-only areas.
- Prefer routing outer UI actions through `_run_long_task` rather than changing command arguments first.
- Do not touch reports, PDFs, payments, balances, 7x7, renewals, collectors, database migrations, cash-control, or report math from this audit alone.
