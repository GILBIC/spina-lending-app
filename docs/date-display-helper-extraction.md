# Date display helper extraction

This extraction moves two low-risk date helpers from the SPINA desktop source into the existing `spina_app/utilities/dates.py` module.

## Extracted helpers

- `_spina_dash__date_text`
- `_spina_v24_cilog_parse_day`

## Preserved behavior

The original function names, signatures, source bodies, return types, and fallback behavior are preserved. Existing callers continue using the same names.

The behavior fixture covers:

- empty and whitespace-only values
- valid `YYYY-MM-DD` dates
- date-time strings beginning with `YYYY-MM-DD`
- invalid dates and unsupported date formats
- Python `date` and `datetime` objects
- non-date numeric input

## Safety boundaries

This extraction does not change:

- payment entry or allocation
- balances, principal, interest, or 7x7 calculations
- renewals or advance/pass behavior
- PostgreSQL or database access
- reports or PDF generation
- authentication or roles
- Tkinter callbacks

`_spina__norm_dom` was reviewed but deliberately left in the main app because it may participate in payment-schedule rules.

## Validation

The guarded extractor:

- rejects decorators and global/nonlocal state
- verifies both functions retain one simple argument
- permits only the existing `_spina_dash__parse_date` helper and Python's `datetime` class as dependencies
- compiles the complete app and updated utility module
- rejects partial or mixed extraction states

The permanent quality workflow runs the behavior regression on every pull request.
