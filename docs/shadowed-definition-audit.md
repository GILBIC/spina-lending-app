# Shadowed definition audit

This document describes the read-only tool for reviewing duplicate and shadowed definitions in the SPINA app.

## Why

The post-logging quality report still shows many duplicate top-level definitions, duplicate class methods, and repeated patch targets. These are not safe to delete blindly because some are compatibility wrappers, monkey patches, or protected business/report logic.

The safe next step is to create a report that separates:

- duplicate top-level function names
- duplicate class method names
- repeated monkey-patch targets such as `App.refresh_clients`
- first review candidates where earlier definitions appear shadowed and are not in protected context

## Tool

Run:

```bat
python tools\audit_shadowed_definitions.py --json shadowed-definition-report.json
```

Then review the JSON before any cleanup.

## Safety rules

The tool is read-only. It does not edit the app.

Do not remove code based only on name duplication. Review one duplicate family at a time and avoid protected contexts such as balances, 7x7, interest, payment allocation, notes, collector route, statements, PDFs, renewals, and report math.

Repeated monkey patches should be consolidated only after checking which patch is active and whether the earlier patch is still needed as a fallback.
