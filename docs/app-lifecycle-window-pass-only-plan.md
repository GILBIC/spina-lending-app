# App lifecycle/window pass-only planner

This document describes `tools/plan_app_lifecycle_window_pass_only.py`.

## Purpose

The planner narrows remaining pass-only exception review to small App lifecycle/window fallback handlers, such as startup window geometry fallback and root-closing watchdog fallback.

It is intentionally read-only and does not approve cleanup.

## Safety rules

- Does not modify the SPINA app source.
- Keeps `selected_cleanup_candidate_count` at `0`.
- Treats App lifecycle/window fallback handlers as review-only.
- Does not touch reports, PDFs, payments, balances, 7x7 calculation logic, renewals, collectors, backups, PostgreSQL, database migrations, cash-control, role/access logic, login/auth, or report math.

## Local use

After this PR is merged and `main` is pulled:

```bat
python tools\plan_app_lifecycle_window_pass_only.py --json app-lifecycle-window-pass-only-plan.json
```

Upload the JSON report before any cleanup tool is considered.

## Expected decision process

1. Review the narrowed App lifecycle/window sites.
2. Confirm they are only startup/window/root-closing fallbacks.
3. Leave them alone unless a later exact cleanup tool can prove the behavior is unchanged.
