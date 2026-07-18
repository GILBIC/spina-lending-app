# UI/action inventory cleanup workflow

This document describes the safe next step before deleting old SPINA UI code.

## Purpose

The desktop app has grown through many patch layers. Some buttons and callbacks are now legacy, but the source also contains business-critical logic for balances, 7x7, payments, notes, and reports.

Before deleting old code, run an inventory so we know what is probably UI/action glue and what must be protected.

## Tool

```bat
python tools\ui_action_inventory.py "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py" --json ui-action-inventory.json
```

The tool scans for old UI/action groups such as:

- Clients legacy actions
  - From Transactions
  - Full Ledger
  - Export Template
  - Import Excel
- Data Bank export controls
  - Exports
  - Date Range Template
  - JSONL Month
  - Daily Excel Template

## Safety rules

Do not delete code when the surrounding context includes:

- balance
- 7x7
- principal
- interest
- payment allocation
- advance/pass
- collector route
- notes
- client statement or report math

Delete only confirmed UI/action glue first.

## Suggested cleanup order

1. Confirm unwanted buttons are no longer visible.
2. Inventory matching labels, callbacks, and command references.
3. Mark items as KEEP, REMOVE, UNKNOWN, or DANGER.
4. Delete only the REMOVE group in small PRs.
5. Smoke test login, Clients, Data Bank, Reports, Collector Route, and Backup.

## Why this is safer

Removing old visual controls is low risk. Removing shared helpers or report/payment calculations is high risk. This inventory helps separate those areas before we do real deletion.
