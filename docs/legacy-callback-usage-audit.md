# Legacy callback usage audit

This read-only audit is the next step after the old Clients and Data Bank UI controls were removed.

## Why

The refined UI/action inventory showed:

- no exact old Clients legacy action labels
- no old Data Bank export labels
- no command references for either removed UI group
- nine callback-name matches still remain

Those remaining callback-name matches should not be deleted directly. Some are shared app functions, report generators, Excel helpers, or protected code areas.

## Tool

```bat
python tools\audit_legacy_callback_usage.py --json legacy-callback-usage-report.json
```

The tool reports for each remaining callback-like name:

- definition lines
- function size
- external references
- command references
- protected-context references
- a conservative recommendation

## Safety

This tool is read-only. It does not modify the app source.

Do not delete functions that touch:

- balances
- 7x7
- principal
- interest
- payment allocation
- advance/pass
- collector route
- notes
- client statements
- report math

Only delete a function later when the audit shows no external references and the function is manually confirmed to be old UI glue, not business logic.
