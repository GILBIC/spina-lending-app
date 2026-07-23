# UI display helper batch 02

This accelerated batch extracts five related display-only helpers from the large SPINA desktop source into `spina_app/ui_helpers.py`.

## Helpers

- `_spina_v20_round_rect`
- `_spina_v24_cilog_round_rect`
- `_spina_v18_draw_round_rect`
- `_spina_v17_set_card`
- `_spina_v24_cilog_set_card`

## Safety boundary

The helpers only call an already-provided canvas or update already-created label widgets. They do not query or modify PostgreSQL, files, payments, balances, principal, interest, 7x7 calculations, renewals, reports, PDFs, authentication, roles, or business rules.

The manifest-driven extractor verifies each exact source hash, signature, dependency list, destination, and source/extracted state independently.

The regression fixture records:

- polygon drawing calls and return values
- fallback rectangle calls after polygon errors
- custom radius and keyword forwarding
- card value and subtitle updates
- missing keys and missing card maps
- existing exception-swallowing behavior for widget failures

Permanent read-only CI compiles the extracted module and compares every saved behavior case on each pull request.

## Desktop smoke test

1. Launch SPINA and log in.
2. Open Dashboard and confirm cards and rounded chart backgrounds display normally.
3. Open Audit Trails / Client Information Log and confirm cards and chart panels display normally.
4. Resize or refresh those screens once and confirm no drawing error appears.
