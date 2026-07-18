# Pass-only exception audit

This is a read-only audit for `except ...: pass` handlers in the SPINA desktop app.

## Purpose

The quality audit shows many silent pass-only exception handlers. These should not be changed blindly because many are inside protected business logic, UI compatibility paths, or database paths.

This audit reports:

- total pass-only exception handler count
- protected versus non-protected context counts
- handler type, such as `Exception`, bare, or other named exception
- surrounding source context for review

## Safety

This tool does not edit the app source. Any cleanup should be planned from the JSON report first.

Do not use this audit alone to change payments, balances, 7x7, renewals, collectors, reports, backups, database migrations, cash-control, or report math.

## Local use

```bat
python tools\audit_pass_only_exceptions.py --json pass-only-exception-report.json
```

Upload the JSON report before any cleanup is attempted.
