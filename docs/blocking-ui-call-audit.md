# Blocking UI Call Audit

This is a read-only audit for possible UI freezes in the SPINA desktop app.

## Why this exists

The post-neutral-cleanup quality report still shows a small set of possible blocking calls:

- `time.sleep`
- `subprocess.run`

Blocking calls are safer to review than protected report, payment, collector, balance, 7x7, renewal, or database patch chains because this audit only reports locations. It does not change behavior.

## Run locally

After pulling `main`, run:

```bat
python tools\audit_blocking_ui_calls.py --json blocking-ui-calls-report.json
```

Upload `blocking-ui-calls-report.json` before changing code.

## Safety rules

Do not make automatic edits from this report.

Treat every result as review-only until the surrounding function is checked. Some calls may be safe if they already run inside a worker thread, background task, or diagnostic path.

Do not touch reports, PDFs, payments, balances, 7x7, renewals, collectors, database migrations, cash-control, or report math based only on this audit.

## What to check after any future change

After a confirmed safe change, run:

```bat
python -m py_compile "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
python "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
```

Then smoke-test:

- Login
- Dashboard
- Clients
- Data Bank
- Reports
- Collector Route
- Any feature around the changed call
