# Data Bank export callback cleanup

This cleanup step is for removing the old Data Bank export callback functions after the visible Data Bank export strip has already been removed.

Target callbacks:

- `export_jsonl_month`
- `export_daily_collection_template`

## Why this is separate

The UI buttons were removed first. The callback functions are removed only after checking that no remaining source lines still reference them.

This avoids deleting code that is still wired somewhere else.

## Local use after merge

Use GitHub Desktop to discard unrelated local changes and pull `main` first.

Then run:

```bat
python tools\cleanup_databank_export_callbacks.py
python -m py_compile "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
python "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
```

## Safety behavior

The tool is conservative:

- it scans for the target function definitions
- it scans for references to those function names outside their own definitions
- if any outside reference remains, it stops and prints the lines
- it only deletes the target function bodies when no outside references are found

## Not changed

This cleanup does not change:

- notes storage or note rendering
- Collector Route Daily Ledger
- Client Statement PDF
- balances
- 7x7
- interest
- payment allocation
- report math
- database writes
