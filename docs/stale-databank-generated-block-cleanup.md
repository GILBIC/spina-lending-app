# Stale Data Bank generated block cleanup

This cleanup step is for removing leftover generated Data Bank export hide/destroy blocks after the visible Data Bank export controls and old callbacks have already been removed.

## Why this is separate

Earlier cleanup tools used runtime hide/destroy fallback blocks to remove visible Data Bank export controls safely. After the UI source lines and callbacks are gone, those generated fallback blocks can become leftover patch code.

This tool is intentionally two-step:

1. It first prints the exact candidate line ranges.
2. It removes them only when run with `--apply`.

## Older generated block shapes

Some older generated blocks do not contain the newer comment text used by later cleanup tools. The tool can recognize those older shapes when they still contain Data Bank export labels or callback-name strings together with generated hide/destroy behavior.

It still stops if a reference looks like a real call site instead of generated fallback cleanup code.

## Large generated fallback blocks

One older generated fallback block can be slightly larger than the original review limit. The tool now allows a larger generated-block range only when these checks pass:

- it still contains Data Bank export cleanup markers or labels
- it still contains generated hide/destroy behavior
- it does not contain protected lending/report logic terms in executable code
- the range is still below the extended safety limit

Large accepted ranges are printed with a `[SPINA][REVIEW]` note during dry run before `--apply` is used.

## Comment-only protected terms

The tool may see protected words such as `balance`, `7x7`, or `collector route` in comments that document what the cleanup must not touch. Those comment-only safety notes are not executable lending/report logic, so the tool can ignore them and print a `[SPINA][REVIEW]` note.

Protected terms inside executable code or string values still stop the cleanup.

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
- candidate blocks are small enough to review or pass the stricter large-block checks
- candidate blocks do not contain protected lending/report logic terms in executable code

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
