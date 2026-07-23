# Numeric parser extraction

This extraction moves two small numeric-conversion helpers from the large SPINA desktop source into `spina_app/utilities/numbers.py`.

## Extracted helpers

- `_spina_dash__float`
- `_spina_v27_count_from_text`

## Preserved behavior

The exact original function bodies and names are retained. Existing callers continue using the same global names through same-name imports placed where the original definitions existed.

`_spina_dash__float`:

- converts numeric values and numeric text to `float`
- removes commas before conversion
- supports its existing optional fallback value
- returns the fallback for invalid input

`_spina_v27_count_from_text`:

- finds the first sequence of digits in text
- returns that sequence as an integer
- returns zero when no digits are present

## Dependency boundary

The module uses only Python's standard `re` library. The guarded extractor rejects decorators, global or nonlocal state, unsupported external names, duplicate or missing functions, mixed extraction states, module conflicts, and compilation failures.

## Excluded areas

This extraction does not alter:

- PostgreSQL or database operations
- payment entry or allocation
- balances, interest, or 7x7 calculations
- renewals
- reports or PDFs
- payroll, authentication, permissions, or backups
- Cash Control amount parsing

## Regression coverage

The committed fixture checks empty input, spaces, integers, negative values, decimals, numeric text, comma-formatted text, invalid text, and boolean input. Permanent read-only CI compiles the app and utility module and reruns the behavior comparison.

## Desktop smoke test

1. Launch SPINA and log in.
2. Open Dashboard and confirm numeric cards load normally.
3. Open the screen that displays the V27 count label and confirm the count appears normally.
4. No payment entry, report generation, or database modification is required.
