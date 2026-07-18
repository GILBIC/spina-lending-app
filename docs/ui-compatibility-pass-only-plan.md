# UI compatibility pass-only planner

This document describes `tools/plan_ui_compatibility_pass_only.py`.

## Purpose

After the modern UI pass-only cleanup, the remaining pass-only exception handlers should not be cleaned together. Some are safe lifecycle fallbacks, some are logger fallbacks, and some are near sensitive business workflows.

This planner focuses only on pass-only exception handlers that look like UI compatibility fallbacks, such as:

- best-effort Tk/Ttk window setup
- geometry, transient, grab, resizable, bind, style, and tag setup
- dialog/window compatibility code
- UI-only widget refresh fallbacks

## Safety

The planner is read-only.

It does not edit the SPINA app source.

It does not approve cleanup.

It sets `selected_cleanup_candidate_count` to `0` so any later cleanup still requires a separate reviewed plan and separate tool.

Protected contexts remain review-only. The planner treats nearby protected words as unsafe for automatic cleanup, including payment, balance, report, collector, backup, PostgreSQL, renewal, transaction, 7x7, and other business-critical terms.

## Local use

Run from the repository root:

```bat
python tools\plan_ui_compatibility_pass_only.py --json ui-compatibility-pass-only-plan.json
```

Upload the JSON report for review before any cleanup tool is created.

## Review rule

Do not clean everything in the UI compatibility group.

Only a very small subgroup should be considered later, and only after the JSON report shows it is clearly UI-chrome-only and not close to client data, Data Bank, reports, payments, roles, 7x7, backups, or PostgreSQL logic.
