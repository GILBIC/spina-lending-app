# Stale Data Bank generated block cleanup

This cleanup step is for removing leftover generated Data Bank export hide/destroy blocks after the visible Data Bank export controls and old callbacks have already been removed.

## Why this is separate

Earlier cleanup tools used runtime hide/destroy fallback blocks to remove visible Data Bank export controls safely. After the UI source lines and callbacks are gone, those generated fallback blocks can become leftover patch code.

This tool is intentionally two-step:

1. It first prints the exact candidate line ranges.
2. It removes them only when run with `--apply`.

## Older generated block shapes

Some older generated blocks do not contain the newer comment text used by later cleanup tools. The tool can now recognize those older shapes when they still contain Data Bank export labels or callback-name strings together with generated hide/destroy behavior.

It still stops if a reference looks like a real call site instead of generated fallback cleanup code.

## Local use after merge

Use GitHub Desktop to pull `main` first.

Dry run:

```bat
python tools\cleanup_stale_databank_generated_blocks.py
```

If it prints safe candidate ranges, apply the cleanup:

```bat
python tools\cleanup_stale_databank_generated_blocks.py --apply
python -m py_compile "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
python "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
```

## Safety behavior

The tool refuses to remove anything unless:

- the old Data Bank export callback definitions are already gone
- all remaining callback-name references are inside generated Data Bank cleanup/hide blocks
- candidate blocks contain expected generated hide/destroy code markers
- candidate blocks are small enough to review
- candidate blocks do not contain protected lending/report logic terms

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
