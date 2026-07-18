# Data Bank export UI source cleanup

This cleanup is based on `ui-action-inventory.json`.

The inventory found exact Data Bank export UI command references for:

- `export_jsonl_month`
- `export_daily_collection_template`

It also found the visible export strip labels/buttons:

- Exports
- Date Range Template
- JSONL Month
- Daily Excel Template

## Why this cleanup is narrow

The first real delete should remove only visible UI/action glue, not business logic.

The cleanup tool removes Data Bank export label/button creation lines and removes older runtime hide-only Data Bank export blocks if present.

It intentionally keeps the callback functions for now:

- `export_jsonl_month`
- `export_daily_collection_template`

Those functions should only be deleted after a later inventory confirms they have no remaining command references or safe internal use.

## Local use after merge

Use GitHub Desktop first:

1. Close SPINA.
2. Go to **Changes**.
3. Discard local app-file changes.
4. Fetch origin.
5. Pull origin.

Then run:

```bat
python tools\cleanup_databank_export_ui_source.py
python -m py_compile "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
python "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
```

Open **Data Bank** and confirm these are gone:

- Exports
- Date Range Template
- JSONL Month
- Daily Excel Template

## Safety

This does not change:

- notes storage
- note rendering
- Collector Route Daily Ledger
- Client Statement PDF
- balances
- 7x7 logic
- interest logic
- payment allocation
- report math
- database writes
