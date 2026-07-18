# Disable Full Daily Ledger

This document describes the safe Full Daily Ledger removal path.

## Purpose

The Full Daily Ledger action is being disabled because the preferred printing path is Collector Route Daily Ledger. This keeps the app simpler and avoids confusion when notes are expected on collector-specific outputs.

## Safety rule

This change does not delete old ledger code directly. It adds a manual injector that disables the Full Daily Ledger action at runtime.

It does not change:

- notes storage
- note rendering logic
- Collector Route Daily Ledger
- loan balances
- 7x7 logic
- interest logic
- payment allocation
- report formulas or math
- database writes

## Local command after merge

Run this from the repository folder:

```bat
python tools\disable_full_daily_ledger.py
python -m py_compile "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
python "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
```

Then check:

1. Full Daily Ledger button/action should be gone or disabled.
2. Collector Route Daily Ledger should still work.
3. Notes should still appear in the collector route output.
4. Client Statement PDF should still work.

## Undo local injected change

The injector modifies the local app file. After testing, you can undo the local injected block:

```bat
git restore "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
git restore docs/code-issue-review.md
```

## Why not delete the huge function immediately?

`print_full_daily_ledger` is a very large legacy function and may still share helpers with other print flows. Disabling the visible action first is safer than deleting thousands of lines in one PR.
