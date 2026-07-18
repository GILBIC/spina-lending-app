# Login-dialog pass-only planner

This document describes `tools/plan_login_dialog_pass_only.py`.

## Purpose

The tool is a read-only planner for pass-only exception handlers around login, authentication, and login-dialog UI code.

It exists because the broader UI compatibility planner found many UI-related pass-only handlers, but only a very small login-dialog subgroup should be considered before any future cleanup.

## Safety rules

- It does not edit the SPINA app.
- It does not approve cleanup.
- `selected_cleanup_candidate_count` is always `0`.
- Password, authentication, role, account, and permission-related handlers remain review-only.
- Protected business-context words keep sites out of cleanup planning.

## Local use

After merging the PR and pulling main:

```bat
python tools\plan_login_dialog_pass_only.py --json login-dialog-pass-only-plan.json
```

Upload the JSON report before any cleanup tool is created.

## Review notes

Potential future cleanup must be limited to a tiny, clearly UI-only login dialog group, if one exists. Do not touch password validation, authentication, account creation, roles, permissions, PostgreSQL login, or app login security from this pass.
