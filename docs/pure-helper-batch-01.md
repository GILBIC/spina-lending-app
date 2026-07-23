# Pure Helper Batch 01

This is the first accelerated modularization batch. It groups four small helpers that only format or parse already-computed display values.

## Helpers

- `_spina__fmt_client_money` → `spina_app/utilities/formatting.py`
- `_spina_v17_fmt_short_money` → `spina_app/utilities/formatting.py`
- `_spina_v18_fmt_money_compact` → `spina_app/utilities/formatting.py`
- `_spina_v25_parse_count_from_var` → `spina_app/utilities/numbers.py`

## Why these four

Each helper:

- is a small top-level function
- has no global or nonlocal state
- does not access PostgreSQL, files, Tkinter widgets, reports, PDFs, payments, balances, interest, 7x7, renewals, authentication, or roles
- does not mutate caller-provided objects
- only converts an input into display text

## Guardrails

The reusable batch extractor verifies every helper separately:

- exact function name and signature
- exact source SHA-256
- no decorators
- no global or nonlocal declarations
- exact allowed external dependencies
- no mixed source/extracted state
- destination function uniqueness
- compilation of the patched app and utility modules

## Regression coverage

The behavior fixture is captured from the original functions before extraction. Tests cover:

- blank and `None` values
- zero, positive, negative, and decimal values
- threshold behavior for thousands, hundred-thousands, and millions
- numeric and invalid text
- booleans and list values
- count labels, leading zeroes, multiple numbers, negative text, and decimal text

## Desktop smoke test

1. Launch SPINA and log in.
2. Open **Clients** and confirm money values display normally.
3. Open **Dashboard** and confirm chart/card money labels display normally.
4. Open **Collector Route** and confirm collector count cards display normally.
5. No payment entry, report generation, or database modification is required.
