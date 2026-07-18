# Neutral AppClass.__init__ patch cleanup

The patch-chain audit found only one non-protected repeated patch target:

```text
AppClass.__init__
```

The reported chain temporarily assigns `patched_init`, then restores `orig_App_init`, so the final effective assignment is the original initializer again.

This document describes the narrow manual tool for reviewing and removing only that no-op patch/restore pair.

## Safety

The tool is intentionally conservative:

- dry run is the default
- edits only when `--apply` is supplied
- targets only the `AppClass.__init__ = patched_init` / `AppClass.__init__ = orig_App_init` neutral pair
- refuses to run if protected words are found in the candidate block
- does not touch `App.__init__`, refresh patches, collectors, dashboard, reports, PDFs, notes, payments, balances, 7x7, renewals, cash-control, database, or report math
- creates a backup before writing

## Dry run

```bat
python tools\cleanup_neutral_appclass_init_patch.py --json neutral-appclass-init-cleanup-plan.json
```

Review the reported candidate lines before applying.

## Apply only after review

```bat
python tools\cleanup_neutral_appclass_init_patch.py --apply --json neutral-appclass-init-cleanup-plan.json
python -m py_compile "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
python "OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py"
```

Smoke-test Login, Dashboard, Clients, Data Bank, Reports, Collector Route, and Backup before committing only the app file.
