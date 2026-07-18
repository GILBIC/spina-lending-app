# PostgreSQL command caller audit

This document describes `tools/audit_pg_command_callers.py`.

## Purpose

The blocking UI context report showed PostgreSQL backup/restore command calls that may block the Tkinter UI thread. Before changing app behavior, this read-only audit traces call sites for the backup and PostgreSQL command helper functions.

## Local command

```bat
python tools\audit_pg_command_callers.py --json pg-command-callers-report.json
```

## Safety rules

- The tool is read-only.
- It does not edit the main app source.
- It reports definitions and call sites for PostgreSQL command helpers.
- It marks whether each caller appears to use an existing long-task or worker path.
- It treats backup, restore, PostgreSQL, database, reports, payments, balances, collectors, renewals, cash-control, and related source context as protected review-only areas.

## What to do with the report

Upload `pg-command-callers-report.json` before any cleanup is attempted.

A UI-freeze fix should only be attempted after the call flow proves which backup/restore action is still running on the UI thread. Any fix should be one small change family at a time and must be smoke-tested with backup, verify backup, and restore-test flows.
