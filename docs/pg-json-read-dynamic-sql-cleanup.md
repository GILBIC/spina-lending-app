# PostgreSQL JSON read dynamic SQL cleanup

This document describes the narrow cleanup helper in:

```text
tools/cleanup_pg_json_read_dynamic_sql.py
```

## Why this exists

The dynamic SQL context audit found exactly one non-protected dynamic SQL site:

```python
cur.execute(f'SELECT value FROM {table} WHERE key=%s', (key,))
```

This is in `_spina_pg_read_json`. The table name comes from `_spina_pg_json_table_for_path`, which currently returns only:

- `app_settings_store`
- `app_json_store`

The matching write helper already uses fixed-table branches. This cleanup makes the read helper follow the same pattern.

## Dry run

Run from the repo root:

```bat
python tools\cleanup_pg_json_read_dynamic_sql.py --json pg-json-read-cleanup-plan.json
```

Review the JSON. It should show:

```json
"safe": true,
"candidate_count": 1
```

## Apply

Only apply after the dry run is safe:

```bat
python tools\cleanup_pg_json_read_dynamic_sql.py --apply --json pg-json-read-cleanup-after.json
```

## Verify

After applying, run:

```bat
python tools\audit_dynamic_sql_context.py --json dynamic-sql-context-after-pg-json-cleanup.json
```

The expected result is that the single non-protected dynamic SQL site is gone. Protected dynamic SQL sites are still review-only.

## Safety rules

- This tool targets only `_spina_pg_read_json`.
- It does not touch payments, balances, 7x7, reports, collectors, renewals, backups, restore logic, or database migrations.
- It should not be used for broad SQL rewriting.
