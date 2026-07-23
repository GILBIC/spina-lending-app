# Display/UI helper batch 04

This accelerated batch extracts three display-only helpers from the large SPINA desktop source.

## Helpers

- `_spina_dash__fmt_money` → `spina_app/utilities/formatting.py`
- `_spina_cashctl__fmt_pct` → `spina_app/utilities/formatting.py`
- `_spina_v21_cash_set_card` → `spina_app/ui_helpers.py`

## Safety boundary

The helpers only format or display values that were already computed elsewhere. They do not query or modify PostgreSQL, allocate payments, calculate balances, principal, interest, or 7x7 values, process renewals, calculate report totals, generate PDFs, authenticate users, check roles, or execute callbacks.

Each original top-level definition is replaced by a same-name import. Existing callers remain unchanged, and the extracted module contains the exact original body.

## Regression coverage

- Dashboard money formatting for empty, numeric, negative, text, invalid, and boolean inputs
- Cash Control percentage formatting for empty, numeric, negative, text, invalid, and boolean inputs
- Cash Control card value and subtitle updates
- missing card keys and missing card maps
- preserved exception-swallowing behavior when label updates fail

## Desktop smoke test

1. Launch SPINA and log in.
2. Open Dashboard and confirm money values display normally.
3. Open Cash Control and confirm percentage labels and summary cards display normally.
4. Refresh or resize Cash Control once and confirm no display error appears.
