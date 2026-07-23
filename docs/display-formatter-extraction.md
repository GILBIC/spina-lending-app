# Display formatter extraction

This modularization step moves three pure display-formatting helpers from the large SPINA desktop source into `spina_app/utilities/formatting.py`:

- `_spina_dash__fmt_pct`
- `_spina_v23_money`
- `_spina_v23_percent`

Each original top-level definition is replaced with a same-name import. Existing callers are unchanged.

## Safety boundaries

This extraction does not change:

- PostgreSQL or database access
- payments or payment allocation
- balances, interest, or 7x7 calculations
- renewals
- reports or PDF generation
- collectors or routes
- backups
- authentication or role access
- Tkinter callbacks

The guarded extractor rejects decorators, global or nonlocal state, external loaded names, duplicates, partial extraction states, compilation failures, and missing or conflicting formatting-module definitions.

## Regression coverage

The behavior fixture records the exact output or exception behavior for:

- empty and `None` values
- zero, positive, negative, and decimal numbers
- numeric and invalid text
- comma-formatted text
- boolean input

The permanent quality workflow compiles the app, utility modules, extractor, and test, then runs the formatter regression test.

## Desktop smoke test

After CI passes:

1. Launch SPINA.
2. Log in normally.
3. Open Dashboard.
4. Confirm percentages display normally.
5. Open any screen using the modern dashboard money/percent cards and confirm values appear unchanged.

No payment entry, report generation, or database modification is required for this extraction.
