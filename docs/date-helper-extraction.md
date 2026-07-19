# Date helper modularization

This change moves three small, pure date helpers from the 48,000-line desktop application into:

```text
spina_app/utilities/dates.py
```

## Extracted helpers

- `_spina_cashctl__valid_date`
- `_spina__parse_day_ymd`
- `_spina_dash__parse_date`

The original global names remain available through imports placed where each function definition previously appeared. Existing callers are unchanged.

## Why these helpers

The module-separation planner classified these helpers as low risk. They have no shared application-global reads and no calls to other top-level SPINA definitions. Their only external dependency is the Python standard-library `datetime` import already used by the original source.

## Guardrails

`tools/extract_date_helpers_module.py` refuses to apply when:

- any selected helper is missing or duplicated
- the source is in a mixed or partially extracted state
- a selected helper has decorators
- a selected helper uses `global` or `nonlocal`
- an external loaded name is not provided by a standard-library import
- the generated module or patched application does not compile
- an existing different `dates.py` would be overwritten

The extractor is dry-run by default and is idempotent after a successful application.

## Regression coverage

`tools/test_date_helpers_extraction.py` checks representative valid, invalid, empty, object, and malformed date inputs. The fallback that intentionally returns the current date is normalized as `<TODAY:%Y-%m-%d>` so the fixture remains valid across days.

The permanent quality workflow compiles the application, both extracted utility modules, the extractor, and the regression test, then runs the regression test.

## Explicitly unchanged

This extraction does not change database access, PostgreSQL storage, payments, balances, interest, 7x7 logic, renewals, reports, PDFs, collector routes, payroll, authentication, role access, backups, or Tkinter callbacks.
