# Text normalizer extraction

This change moves three pure text-normalization helpers from the large SPINA desktop source into:

```text
spina_app/utilities/text.py
```

Extracted helpers:

- `_oslp__norm_area_name`
- `_spina_crc_norm_text`
- `_spina_route_notice_norm_name`

## Behavior preservation

The original function names and bodies are preserved. Each old top-level definition is replaced at the same location with a same-name import, so existing callers do not change.

The regression fixture checks:

- empty and whitespace-only values
- leading, trailing, and repeated spaces
- mixed letter case
- symbols and punctuation
- Unicode text
- numeric and boolean inputs

## Safety boundary

This extraction does not change:

- PostgreSQL or database access
- payment allocation or balances
- interest, 7x7, or renewal rules
- reports or PDF generation
- collector-route behavior
- authentication or role access
- Tkinter callbacks

The guarded extractor refuses decorators, global/nonlocal state, duplicate or missing definitions, non-standard-library dependencies, partial extraction states, and compilation failures.

## Desktop smoke test

1. Launch SPINA and log in.
2. Open Clients and confirm area names display normally.
3. Open Collector Route and confirm client/collector names display normally.
4. No payment entry or database modification is required.
