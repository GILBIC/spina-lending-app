# CILOG diff-pairs helper extraction

This extraction moves `_spina_cilog_diff_pairs` from the large desktop application source into `spina_app/utilities/diffs.py`.

## Purpose

The helper compares already-loaded old and new audit/history values and returns field-level differences for display.

## Production change

- The original top-level function definition is replaced by a same-name import.
- The exact original function body is stored in `spina_app/utilities/diffs.py`.
- The existing caller in `_spina_cilog_fetch_rows` is unchanged.

## Guardrails

The extractor refuses to proceed when it finds:

- an unexpected signature
- decorators
- global or nonlocal state
- external dependencies
- duplicate definitions
- a mixed partially extracted state
- compilation failures

## Regression coverage

The saved fixture covers:

- both values missing
- whole records added or removed
- scalar changes and unchanged scalars
- dictionary-to-scalar comparisons
- empty records
- `id`-only changes
- sorted changed fields
- added and removed keys
- nested dictionaries and list values
- Python equality behavior for booleans and numbers
- changes involving `None`

No database, payment, balance, interest, 7x7, report, PDF, authentication, or UI callback logic is changed.
