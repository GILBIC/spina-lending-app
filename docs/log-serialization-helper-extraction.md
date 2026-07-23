# Log serialization helper extraction

This extraction moves one isolated Client Information Log JSON helper into a reusable utility module.

## Extracted helper

- `_spina_cilog_safe_json`

## Destination

- `spina_app/utilities/serialization.py`

## Preserved behavior

The function body and name are unchanged. It:

- returns `None` for `None` and empty text
- returns dictionaries unchanged
- parses valid JSON through Python's standard `json.loads`
- returns `None` when parsing fails

## Safety boundary

The extraction does not change:

- PostgreSQL or database queries
- client information log row selection
- payments, balances, interest, principal, 7x7, or renewals
- reports or PDFs
- authentication, roles, or access control
- Tkinter callbacks or UI layout

The helper has one production caller, `_spina_cilog_fetch_rows`. Existing callers continue using the same function name.

## Verification

The committed regression fixture covers dictionaries, JSON objects, lists, numbers, booleans, null values, bytes, invalid text, integers, and empty input. Permanent read-only CI compiles the app and utility module and compares current behavior with the saved fixture.
