# Silent UI logging injector

This document describes the manual tool for adding log-once messages to safe silent UI/startup exception handlers.

## Why

The silent UI error audit reported many silent handlers. Most are in protected business areas and should not be edited first. The safe next step is to add visibility only to small non-protected UI/startup/loading fallbacks.

The first dry-run plan was too broad because it selected PostgreSQL storage, file/path helpers, reports/PDF-related setup, and notes. Do **not** apply that older plan.

## Tool

Dry run first:

```bat
python tools\inject_silent_ui_logging.py --json silent-ui-logging-plan.json
```

Review `silent-ui-logging-plan.json` before applying. The tightened tool skips broad protected areas, including PostgreSQL storage, file-opening/storage helpers, reports/PDFs, notes, collectors, transactions, and loan/payment logic.

Apply a small first batch only after reviewing the dry run:

```bat
python tools\inject_silent_ui_logging.py --limit 25 --apply --json silent-ui-logging-plan.json
python -m py_compile "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
python "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
```

## Safety rules

The tool is conservative:

- dry run is the default behavior
- edits only when `--apply` is supplied
- changes at most `--limit` handlers in one run
- skips protected contexts such as balances, 7x7, interest, payment allocation, notes, collector route, statements, PDFs, reports, PostgreSQL storage, transactions, and report math
- inserts logging before the existing fallback behavior, without deleting the fallback
- creates a backup file beside the app source before writing

## Smoke test after apply

Check:

- Login
- Dashboard
- Clients
- Data Bank
- Reports
- Collector Route
- Backup

Open the console/log file if something fails. The purpose of this change is to make hidden UI/startup failures visible without changing loan logic.
