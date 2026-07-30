# Data Bank modularization Wave 82

Wave 82 will complete the Data Bank feature boundary while preserving current behavior.

Planned ownership:

- `spina_app/repositories/data_bank.py`: transaction reads/writes, day-close records, audit queries, and backup-safe delete operations.
- `spina_app/services/data_bank.py`: value parsing, ADV/PASS interpretation, date/month helpers, close-state decisions, and row transformations.
- `spina_app/data_bank_controller.py`: grid refresh, cell editing, day close/reopen/delete actions, filters, imports, exports, and audit refresh.
- `spina_app/data_bank_auto_close.py`: configurable auto-close scheduling and settings integration.
- `spina_app/tabs/data_bank_shell.py`: existing presentation/layout helpers.
- `spina_app/features/data_bank.py`: one idempotent installer for final `LoanDB` and `App` bindings.

Safety rules:

- Preserve the combined Regular + 7x7 daily close bucket.
- Preserve append-only transaction and day-close audit history.
- Preserve backup-before-delete behavior.
- Preserve ADV/PASS display and import semantics.
- Preserve fixed-principal 7x7 financial calculations.
- Keep the production desktop source unchanged until generated extraction passes twice and all compatibility tests are green.
- Validate Wave 74 fixed-principal report rules against either the legacy desktop report block or the Wave 80 modular `spina_app/report_engine.py` implementation; the compatibility porter must be idempotent for both layouts.
