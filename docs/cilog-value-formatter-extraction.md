# Client Information Log value formatter extraction

This extraction moves one isolated audit/history display formatter into the existing formatting utility module.

## Extracted helper

- `_spina_cilog_fmt_value`

## Destination

- `spina_app/utilities/formatting.py`

## Preserved behavior

The function name and body are unchanged. It continues to:

- show money fields with commas and two decimal places
- show fractional interest rates as percentages
- preserve already-percent-style interest values
- remove line breaks and outside spaces from ordinary text values
- return an empty string for `None`

## Safety boundary

This change does not alter database access, payment allocation, balances, principal, interest calculations, 7x7 logic, renewals, reports, PDFs, authentication, roles, or Tkinter callbacks. The helper only formats values that have already been loaded for display.

## Verification

The committed behavior fixture covers principal and payment amounts, negative values, numeric text, interest-rate formats, invalid rates, line breaks, outside spaces, lists, empty fields, and `None`. Permanent read-only CI compiles the app and utility module and compares current behavior against that fixture.
