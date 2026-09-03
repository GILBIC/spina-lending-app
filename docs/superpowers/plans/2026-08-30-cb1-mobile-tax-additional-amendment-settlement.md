# CB1 Mobile Additional-Tax Amendment and Settlement Implementation Plan

> Execute locally and stack on the verified Mobile settlement/correction slice. Do not perform production writes, SQL migration execution, merging, deployment, signing, release, or human acceptance completion.

## Task 1: Freeze the backend contract test-first

- Require same-handler Mobile aliases for the seven existing Desktop endpoints.
- Require a server-derived candidate dataclass/query/payload and read response coordinates: filter, pagination, policy flags, items, summary, permissions, notice, and candidates.
- Assert every mutation still calls only the existing protected PostgreSQL functions.
- Run the focused backend test to record red before implementation.

## Task 2: Add read-only candidate derivation and shared handlers

- Add an immutable candidate type and exact eligibility query to the existing repository.
- Serialize candidate fields and add `/api/mobile/v1/...` decorators to the existing handlers.
- Keep Management, approved-device, permission, confirmation, and database write authority unchanged.
- Run focused backend tests and compile/import checks.

## Task 3: Build strict Flutter domain and HTTP contracts test-first

- Add failing model/repository tests for overview, summary, candidate, queue states, permissions, policy flags, all six mutations, headers, and exact request coordinates.
- Implement strict models and one repository that uses only Mobile aliases and candidate/server-returned values.
- Run focused Dart tests.

## Task 4: Add the Management Mobile workspace test-first

- Add failing launcher and widget tests for discoverability, candidate rows, queue actions, permission intersection, separate evidence/prepare/post confirmations, non-editable required payment, and ambiguous-write refresh locking.
- Implement the compact Additional Tax page and connect it from Tax Accounting.
- Register the mutation surface in the Management review inventory without weakening confirmation rules.
- Run focused widget tests and analyzer.

## Task 5: Verify and review the exact slice

- Run focused backend and Flutter suites, formatters, analyzer, Python compile checks, full Flutter regression, and full backend regression with worktree-pinned `PYTHONPATH`.
- Inspect diff/status, run secret-pattern and whitespace checks, and prove the unrelated `architecture-map.json` deletion remains untouched and unstaged.
- Review against accounting authority, lifecycle, permission, device, stale-state, and ambiguous-write invariants.

## Task 6: Publish evidence without closing protected gates

- Commit explicit slice files, push the stacked `codex/` branch, and open a draft PR against the exact preceding Mobile tax branch.
- Wait for exact-head GitHub Actions and record workflow evidence.
- Update the draft PR, Master Issue #296, and authoritative Notion status with current implemented behavior, remaining scope, and still-open human/merge/migration/release gates.
