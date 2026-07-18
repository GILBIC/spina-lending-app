# Remaining pass-only grouping audit

This document describes `tools/plan_remaining_pass_only_groups.py`.

## Purpose

The modern UI pass-only cleanup removed the 19 selected UI chrome/sidebar/theme handlers. The remaining non-protected pass-only exception handlers still should not be changed blindly.

This tool creates a read-only grouping report so the remaining handlers can be separated into small review buckets.

## Safety

The tool is read-only and does not edit the SPINA app source.

It groups pass-only handlers into review categories such as:

- protected business/runtime context
- logger fallback
- queue empty normal control flow
- app shutdown/lifecycle behavior
- role/access runtime patch behavior
- performance index maintenance
- dashboard UI behavior
- other UI compatibility behavior

## Local use after merge

```bat
python tools\plan_remaining_pass_only_groups.py --json remaining-pass-only-groups-report.json
```

Upload the JSON before any next cleanup is planned.

## Rules

Do not clean all remaining handlers together.

Leave logger fallback, queue-empty normal control flow, and shutdown/lifecycle handlers alone unless there is a clear bug.

Treat role/access, dashboard, performance-index, and protected business contexts as review-only until a separate narrow plan is created.
