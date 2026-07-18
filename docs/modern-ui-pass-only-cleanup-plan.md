# Modern UI pass-only cleanup planner

This is a narrow, read-only planning tool for the modern UI chrome/sidebar/theme pass-only exception handlers.

## Why

The pass-only exception audit found many `except ...: pass` handlers, but most are protected or too risky to touch globally.

This planner keeps the scope intentionally small:

- modern sidebar navigation
- modern header/theme refresh
- mode toggle UI chrome
- hover/theme helper UI chrome

It excludes protected business areas such as reports, PDFs, payments, balances, 7x7, renewals, collectors, backups, database migrations, cash-control, and report math.

## Run

```bat
python tools\plan_modern_ui_pass_only_cleanup.py --json modern-ui-pass-only-cleanup-plan.json
```

Upload the JSON report before any cleanup tool is created.

## Safety

- read-only only
- does not edit the SPINA app
- uses a narrow scope list and line-window guard
- excludes protected words/context
- produces `selected_sites` for review before any apply tool exists
