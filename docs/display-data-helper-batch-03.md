# Display/data helper batch 03

This accelerated batch extracts three independent pure helpers from the large SPINA desktop source.

## Helpers

- `_spina_dash__status_for` → `spina_app/utilities/dashboard.py`
- `_spina_perf_dict_rows` → `spina_app/utilities/records.py`
- `_spina_crc_fmt_money` → `spina_app/utilities/formatting.py`

## Safety boundary

The helpers only classify already-computed Dashboard values, copy row-like objects into plain dictionaries, or format an already-computed amount for display. They do not perform database writes, payment allocation, balance calculation, interest calculation, 7x7 logic, renewals, report totals, PDF generation, authentication, or role checks.

The manifest-driven extractor verifies every source hash, function signature, dependency list, destination module, and extraction state independently.

## Regression coverage

- Dashboard status thresholds and precedence
- invalid and empty status inputs
- direct and fallback row conversion
- silently skipped invalid rows
- collector-close integer, decimal, blank-zero, invalid, NaN, and infinity formatting

Permanent read-only CI compiles the touched modules and compares every saved behavior case.

## Desktop smoke test

1. Launch SPINA and log in.
2. Open Dashboard and confirm client status labels still look correct.
3. Open Clients and refresh the client list once.
4. Open Collector Route and confirm displayed amounts look normal.
