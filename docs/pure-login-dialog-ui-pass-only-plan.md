# Pure login dialog UI pass-only planner

This document describes `tools/plan_pure_login_dialog_ui_pass_only.py`.

## Purpose

This is a read-only planning tool. It narrows the previous login-dialog pass-only report to the safest possible login UI subgroup: pure dialog shell behavior only.

Examples of pure dialog UI behavior include:

- making the login window transient
- wiring the account combobox trace callback
- binding Return key actions
- applying the modal grab
- positioning the dialog window
- setting initial focus

## What it does not do

The tool does not edit `OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py`.

It does not approve cleanup.

It keeps `selected_cleanup_candidate_count` at `0`.

It does not touch:

- password verification
- password-change-required flow
- auth/account roles
- access or permissions
- user database save/load logic
- account switching
- account header refresh
- reports, PDFs, payments, balances, 7x7, renewals, collectors, backups, PostgreSQL, database migrations, cash-control, or report math

## Local use

After this PR is merged and main is pulled locally, run:

```bat
python tools\plan_pure_login_dialog_ui_pass_only.py --json pure-login-dialog-ui-pass-only-plan.json
```

Upload the generated JSON before any cleanup tool is created.

## Review rule

A future cleanup tool, if any, should be created only after the JSON output is reviewed. It should target exact reviewed pure dialog UI handlers and should not touch login/auth/account business logic.
