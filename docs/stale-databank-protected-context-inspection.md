# Stale Data Bank protected-context inspection

Use this read-only helper when the stale Data Bank generated-block cleanup stops because a candidate block contains protected words such as `balance`, `7x7`, or `collector route`.

The inspector does not edit the app file. It prints the exact local line numbers and nearby context so the block can be reviewed before any cleanup rule is changed.

## Local use after merge

Use GitHub Desktop to pull `main` first.

Then run:

```bat
python tools\inspect_stale_databank_protected_context.py
```

Send the output for review.

## What it checks

The tool reports:

- remaining Data Bank export callback-name references
- candidate generated cleanup range line numbers
- whether the range looks like generated Data Bank cleanup code
- whether expected hide/destroy generated markers are present
- exact protected-term hit lines with nearby context

## Safety

This tool is read-only. It does not change:

- notes storage or note rendering
- Collector Route Daily Ledger
- Client Statement PDF
- balances
- 7x7
- interest
- payment allocation
- report math
- database writes
