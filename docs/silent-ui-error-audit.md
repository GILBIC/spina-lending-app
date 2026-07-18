# Silent UI/startup error audit

This audit is for the next cleanup phase after the old Clients action buttons and Data Bank export controls were removed.

## Why this exists

The old UI/action cleanup is complete enough to stop deleting from that group. The remaining callback-looking functions still have references or protected context, so they should be kept unless a separate manual review proves otherwise.

The safer next quality step is to find silent exception handlers around UI refresh, startup, login, tab building, and loading code. Silent handlers can hide real errors and make debugging hard.

## Tool

Run from the repository root:

```bat
python tools\audit_silent_ui_errors.py --json silent-ui-error-report.json
```

The tool is read-only. It does not edit the app.

## What it reports

- total silent `except` handlers
- UI/startup-focused silent handlers
- protected-context silent handlers
- non-protected UI/startup candidates for review

## Safety rules

Do not start with handlers near:

- balances
- 7x7
- principal
- interest
- payment allocation
- advance/pass
- notes
- statements
- client PDFs
- collector routes
- ledger totals
- report math

Review non-protected UI/startup handlers first. Add logging in small PRs only after the audit output is reviewed.
