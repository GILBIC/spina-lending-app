# SPINA critical-path logging

This document explains the safe error-logging workflow for SPINA.

## Goal

The app already has many older defensive `except Exception` blocks. Some of them intentionally suppress errors so the desktop app does not crash. That makes troubleshooting harder.

This phase adds a guarded tool for critical-path exception logging. It can insert wrappers around selected entry points so unhandled exceptions are written to the normal SPINA log before they are re-raised.

## Covered areas

The injector targets critical entry points such as:

- PostgreSQL startup and connection helpers
- login prompts and verification
- backup and restore helpers
- report and PDF generation
- Excel import entry points

## Safety rules

This phase does not change loan calculations, balances, payment logic, report math, or database write behavior.

The generated wrappers only run when a covered function raises an exception. Successful calls return the original result.

Older internal exceptions that are intentionally swallowed inside a function are not changed by this phase.

## Local use

Run this from the repository folder:

```bat
python tools\inject_critical_path_logging.py
python -m py_compile "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
python "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
```

Then test startup, login, backup, restore, Excel import, and report generation.

When finished testing, remove the local injected block:

```bat
git restore "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
git restore docs\code-issue-review.md
```

## Where logs go

SPINA uses `data/spina_app.log` when its logger is available. Very early startup issues may also print to Command Prompt using the `[SPINA][EARLY]` or `[SPINA][CRITICAL]` prefix.
