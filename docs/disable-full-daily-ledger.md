# Remove legacy Clients-tab action buttons

This document describes the safe removal path for the legacy Clients-tab action buttons shown as:

- From Transactions
- Full Ledger
- Export Template
- Import Excel

## Purpose

These actions are legacy controls in the Clients tab. They can confuse testing because the preferred flows are now the desktop-aligned Clients editor, Collector Route Daily Ledger, Reports/Statement Center, and controlled import tools.

## Safety rule

This PR does not directly delete thousands of lines from the main SPINA source. It adds a manual injector that removes the visible legacy Clients-tab buttons and disables their known old callback entry points.

It does not change:

- notes storage
- note rendering logic
- Collector Route Daily Ledger
- Client Statement PDF
- loan balances
- 7x7 logic
- interest logic
- payment allocation
- report formulas or math
- database writes

## Late-created Clients tab controls

The Clients tab may create some controls after startup or after the tab is opened. The injector now keeps rescanning briefly after startup, after tab changes, after mouse clicks, and after common Clients-tab build/refresh methods run.

This is why the button removal should work even when the buttons appear after the app first opens.

## Local command after merge

Run this from the repository folder:

```bat
python tools\disable_full_daily_ledger.py
python -m py_compile "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
python "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
```

Then check:

1. In the Clients tab, these buttons should be gone: From Transactions, Full Ledger, Export Template, Import Excel.
2. Collector Route Daily Ledger should still work.
3. Notes should still appear in the collector route output.
4. Client Statement PDF should still work.
5. Normal client search/edit/renew should still work.

## Undo local injected change

The injector modifies the local app file. After testing, you can undo the local injected block:

```bat
git restore "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
git restore docs/code-issue-review.md
```

## Why not delete the huge old functions immediately?

Some old functions are very large and may still share helpers with other print/import flows. Removing the visible actions first is safer than deleting thousands of lines in one PR. After this is confirmed working, the next cleanup can remove unreachable code in smaller pieces.
