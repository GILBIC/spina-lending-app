# First module extraction: `fmt_currency`

This is the first deliberately small production-code separation step after the module-separation report.

## Why this function

The planner classified `fmt_currency` as low risk:

- 5 lines
- no shared-global reads
- no calls to other top-level SPINA definitions
- no database, PDF, Tkinter, threading, spreadsheet, or filesystem dependency signal

## Safety design

`tools/extract_fmt_currency_module.py` is dry-run by default. It refuses to apply when:

- there is not exactly one top-level `fmt_currency` definition
- the function has decorators
- the function loads a non-local, non-builtin name
- the generated module or patched application does not compile

When applied, it creates `spina_app/utilities/formatting.py` from the exact existing function source and replaces the original definition with:

```python
from spina_app.utilities.formatting import fmt_currency
```

The global name remains unchanged, so existing callers continue using `fmt_currency` without edits.

## Validation

The regression test applies the extraction to a temporary copy, verifies that the original source is untouched during dry-run, compiles the patched app and generated module, compares representative return/exception behavior, and confirms a second application is a no-op.

## Local commands after merge

First inspect the dry-run:

```bat
python tools\extract_fmt_currency_module.py --json fmt-currency-extraction-plan.json
```

Only after the dry-run reports `safe_to_apply: true`:

```bat
python tools\extract_fmt_currency_module.py --apply --json fmt-currency-extraction-result.json
```

Then run:

```bat
python -m py_compile OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py spina_app\utilities\formatting.py
python tools\test_fmt_currency_extraction.py
```

Commit the generated `formatting.py` and modified application in a separate narrowly scoped PR.
