# Reports/PDF error visibility

This document explains the narrow Reports/PDF diagnostics added for SPINA.

## Why this exists

The quality audit showed that Reports/PDF has a high number of silent broad exception handlers. Reports/PDF is a safer first cleanup area than payment or balance code because the goal is only to make errors easier to see, not to change amounts.

## What the tool adds

`tools/inject_reports_pdf_logging.py` can insert a local diagnostic block into the SPINA desktop source. The inserted block wraps selected Reports/PDF entry points and logs unhandled exceptions before re-raising the same exception.

Covered areas include:

- report root/folder resolution
- report folder opening
- client statement PDF generation
- full daily ledger printing
- collector route ledger printing
- report-generation recording

## Local command

From the repository folder:

```bat
python tools\inject_reports_pdf_logging.py
python -m py_compile "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
python "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
```

Then test only Reports/PDF actions:

- Generate client statement PDF
- Open reports folder
- Print full daily ledger
- Print collector route ledger
- Generate/download statement-related PDFs

## Expected log prefix

When a wrapped Reports/PDF function fails, the console or SPINA log should include a message with:

```text
[SPINA][REPORTS_PDF]
```

or a matching `reports/pdf:` context through the normal SPINA logger.

## Safety rules

This diagnostic does not change:

- loan balances
- 7x7 logic
- interest logic
- payment allocation
- report math/formulas
- database write behavior
- successful Reports/PDF behavior

The wrappers only add logging when an exception escapes a covered Reports/PDF function.

## Cleanup after local testing

The injector changes the local working copy of the main SPINA source. After testing, remove the local diagnostic block with:

```bat
git restore "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
git restore docs/code-issue-review.md
```

Do not commit the locally injected SPINA source unless a separate PR is planned for that exact source change.
