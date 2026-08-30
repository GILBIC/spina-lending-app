# CB1 Mobile Tax Recoverable Realization Implementation Plan

> Execute locally and stack on the verified Mobile additional-tax slice. Do not perform production writes, SQL migration execution, merging, deployment, signing, release, or human acceptance completion.

## Task 1: Freeze both backend contracts test-first

- Require same-handler Mobile aliases for all four refund and all four credit endpoints.
- Require immutable refund and credit candidate types, read-only eligibility queries, serialized payloads, filters, pagination, policy flags, summary, queues, permissions, and notices.
- Prove the two candidate paths exclude competing realization and that credit candidates require exact same-tax-type unpaid posted liabilities.
- Assert every mutation still calls only the six existing protected PostgreSQL functions.
- Run the focused backend contract tests to record red before implementation.

## Task 2: Add read-only candidates and shared handlers

- Add the smallest immutable candidate types and exact eligibility queries to the existing refund and credit repositories.
- Add payload serialization and `/api/mobile/v1/...` decorators to the existing handlers.
- Keep Management role, approved device, action permissions, explicit confirmation, and protected database write authority unchanged.
- Run focused backend tests and Python compile/import checks.

## Task 3: Build strict Flutter domain and HTTP contracts test-first

- Add failing tests for refund and credit overview models, candidates, queue states, permissions, policy flags, exact request bodies, errors, and approved-device headers.
- Implement strict immutable models and repositories that use only the Mobile aliases and server-returned coordinates.
- Reject invalid money, hashes, UUIDs, dates, policy flags, accounts, and lifecycle states.
- Run focused Dart tests.

## Task 4: Add the Management Mobile workspace test-first

- Add failing launcher and widget tests for one compact Tax Recoverable row, two separated workflows, candidate selection, permission intersection, and six action-specific reviews.
- Implement candidate-derived refund/credit evidence forms, queue actions, exact posting confirmations, and non-editable financial coordinates.
- Lock all mutation actions after an ambiguous write until authoritative refresh succeeds.
- Register the protected mutation surface in the Management review inventory.
- Run focused widget tests and strict analyzer.

## Task 5: Verify and review the exact slice

- Run focused backend and Flutter suites, formatters, strict analyzer, Python compile checks, full Flutter regression, and full backend regression with worktree-pinned `PYTHONPATH`.
- Inspect status/diff, run whitespace and secret-pattern checks, and prove the unrelated `architecture-map.json` deletion remains untouched and unstaged.
- Review accounting authority, mutual exclusion, exact-amount, permission, device, stale-state, and ambiguous-write invariants.

## Task 6: Publish evidence without closing protected gates

- Commit only explicit slice files, push the stacked `codex/` branch, and open a draft PR against the exact preceding Mobile tax branch.
- Wait for exact-head GitHub Actions and record workflow evidence.
- Update the draft PR, Master Issue #296, and authoritative Notion status with implemented behavior, verification evidence, remaining scope, and still-open human/merge/migration/release gates.
