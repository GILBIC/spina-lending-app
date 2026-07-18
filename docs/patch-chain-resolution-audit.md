# Patch chain resolution audit

This document describes the read-only audit for SPINA monkey-patch assignment chains.

## Why

The shadowed-definition report showed repeated patch targets, but it also marked almost everything as protected context. That means we should not delete old wrappers or assignments blindly.

The safe next step is to identify the assignment chain order and the final effective assignment for each repeated target.

## Tool

Run after pulling latest `main`:

```bat
python tools\audit_patch_chains.py --json patch-chain-report.json
```

Upload `patch-chain-report.json` before any cleanup is attempted.

## What it reports

The tool reports:

- repeated patch targets such as `App.__init__`, `App.refresh_clients`, and `App.refresh_dashboard`
- assignment order by line number
- final effective assignment for each target
- whether the chain touches protected context
- non-protected repeated chains for manual review

## Safety rules

- read-only audit only
- does not edit the main app source
- no wrapper or assignment is removed
- protected chains are marked as keep/review, not automatic cleanup
- do not touch balances, 7x7, interest, payment allocation, notes, collector route, statements, PDFs, renewals, cash-control, or report math from this report alone
