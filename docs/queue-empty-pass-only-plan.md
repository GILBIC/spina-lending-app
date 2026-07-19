# Queue.Empty Pass-Only Planner

This document describes the read-only queue.Empty pass-only planner.

## Purpose

The planner narrows review to `queue.Empty` exception handlers that only contain `pass`, especially the UI queue pump empty-queue control-flow path.

It does **not** edit the SPINA app and does **not** approve cleanup.

## Why this is separate

`queue.Empty` is often intentional control flow. In the UI queue pump, it can simply mean there is nothing waiting in the queue. Because of that, this category should be reviewed separately and should not be cleaned from a broad pass-only report.

## Local use

```bat
python tools\plan_queue_empty_pass_only.py --json queue-empty-pass-only-plan.json
```

Upload the JSON report before creating any cleanup tool.

## Safety

The planner is read-only and keeps `selected_cleanup_candidate_count` at `0`.

It does not touch:

- reports or PDFs
- payments, balances, 7x7, renewals, or collectors
- backups or restore logic
- PostgreSQL or database migrations
- cash-control or report math
- role/access or login/auth handlers

## Expected review behavior

A future cleanup should only be considered if the report shows exact reviewed handlers and the replacement keeps empty-queue behavior unchanged.
