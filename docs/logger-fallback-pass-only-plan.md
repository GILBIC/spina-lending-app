# Logger fallback pass-only planner

This is a read-only review tool for a very small pass-only exception subgroup: logger fallback handlers.

## Why this exists

After the pure login dialog UI cleanup, the remaining pass-only handlers are mostly protected or broad review areas. The next safe review step is to look at only the tiny logger fallback group before any cleanup tool is considered.

## What it does

Run:

```bat
python tools\plan_logger_fallback_pass_only.py --json logger-fallback-pass-only-plan.json
```

The tool reports:

- total pass-only exception handlers
- pass-only handlers inside `_log_exc`
- pass-only handlers inside `_log_suppressed_once`
- exact source context for logger fallback sites
- safety metadata showing the report is read-only

## Safety

This planner:

- does not edit the SPINA app
- does not approve cleanup
- keeps `selected_cleanup_candidate_count` at `0`
- only groups logger fallback handlers for review
- does not touch reports, PDFs, payments, balances, 7x7 calculation logic, renewals, collectors, backups, PostgreSQL, database migrations, cash-control, role/access logic, or report math

Upload the JSON report before any cleanup tool is created.
