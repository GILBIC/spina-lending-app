# Area text helper batch 05

This accelerated batch moves three area-name helpers from the large desktop source into `spina_app/utilities/areas.py`:

- `split_area_main_sub`
- `join_area_main_sub`
- `_spina_crc_split_area`

The functions keep their exact source bodies and same-name imports replace the original top-level definitions. Existing callers remain unchanged.

The batch is limited to area text parsing and display. It does not change PostgreSQL operations, payments, balances, principal, interest, 7x7 behavior, renewals, report totals, PDF generation, authentication, roles, or callbacks.

Permanent CI verifies:

- exact source hashes and signatures
- destination-module extraction state
- blank and plain area names
- spaced and unspaced separators
- hyphen, slash, pipe, greater-than, colon, em dash, and en dash parsing
- malformed one-sided separators
- multiple-separator precedence
- joining and trimming behavior
- `_spina_crc_split_area` fallback behavior when the shared splitter is missing or raises
