# Audit defect repairs implementation plan

> **For agentic workers:** Use superpowers:executing-plans and test-driven-development for each assigned task. Independent domains use the dispatching-parallel-agents workflow.

**Goal:** Repair the six verified audit findings against deployed main without importing the unfinished accounting expansion.
**Architecture:** Preserve existing authority and immutable financial evidence. Add a forward database guard for uncovered Treasury/Collector sources, one-snapshot reports, exact remittance review binding, and explicit private-state clearing.
**Tech stack:** FastAPI/Python/psycopg/PostgreSQL, Flutter/Dart, Portal JavaScript.
**Spec:** ../checkpoints/code-audit-20261006/SPINA-code-audit.md (relative to the checkout); user's “Fix” authorizes implementation.

## Global constraints

- Baseline a28208085016efe7620d1bd310ed90e031bc1831; production migrations through0140 Office signatures must remain.
- No actual company balances, tax facts, production writes, or automatic deployment.
- Preserve current authority, immutable receipt/journal history, and actual event dates.
- Older clients must receive a clear blocker when they cannot supply required reviewed remittance identity; never silently waive it.
- Only unique loopback disposable test databases; do not drop unrelated databases.
- Tests must demonstrate original failures and correct behavior, including rejection rollback.

## Review focus

- Missing legacy prior state: never manufacture a zero missed count.
- Unchanged retries versus changed receipts/refund releases: reject stale review before locking money.
- Close/source concurrency and late evidence: serialize admission, preserve real facts and show warnings.
- Read denials versus network failure: erase private data on401/403/426, without falsely treating network loss as revocation.
- Compatibility: current deployed Office migration, older clients, existing accepted remittances, and genuine zero-cash PASS cases.

### Task1: Legacy state and SQL filters

Files: collection_void_repository.py; period_close_repository.py; six v1_tax_*_repository.py; focused regression tests.
- [x] Add permanent tests from audit repros; run RED on baseline.
- [x] Require verified prior state for Management and Collector void; preserve known previous receipt fallback where exact.
- [x] Bind LIKE status patterns as parameters, preserving API filter choices.
- [x] Run receipt/reversal/API and all status-filter tests; retain evidence.

### Task2: Android private read denials

Files: client_payments_page.dart, client_loans_page.dart, analogous affected private read pages only where same bug is demonstrated; Flutter tests.
- [x] Promote audited failing widget cases; add loan and network-control coverage.
- [x] Clear private model and related navigation on authoritative denials; use existing shared error classification.
- [x] Verify denied refresh, session change, transport fallback, nested navigation behavior.
- [x] Run affected Flutter tests and scoped analyzer. Coordinate Flutter use with remittance task.

### Task3: Exact remittance review contract

Files: remittance_repository.py, remittance_review_repository.py, remittance_api.py; Dart remittance model/repository/page; Portal and other callers; tests.
Interfaces: preview includes deterministic review_digest; submission requires expected_review_digest; digest covers collector/date, exact reviewed receipts/current versions, cash split, and refund releases. Use existing cryptographic canonicalization conventions.
- [x] Reproduce stale preview at actual repository boundary; include same-total changed membership.
- [x] Revalidate under existing transaction/source locks before writes. Reject missing/stale digest with explicit refresh/update guidance.
- [x] Serialize digest in every supported client; prevent confirmation/retry from changing reviewed identity.
- [x] Run API, PostgreSQL, Portal and Flutter regressions; document compatibility requirement.

### Task4: Consistent reports

Files: financial_statements_repository.py; new test_financial_statement_snapshot_postgres.py.
- [x] Promote deterministic two-session RED from audit.
- [x] Set read-only REPEATABLE READ before first report query.
- [x] Verify report sees100 consistently while next request sees125; retain existing output schema.

### Task5: Source-complete close safeguard

Files: new0141 migration; source status repository/API/client presentation; tests; disposable verifier.
- [x] Reproduce unposted cash accepted at review/prepare/post.
- [x] Port bounded source inventory/locks from retained accounting branch as a forward migration after Office0140; do not enable adapters or invent postings.
- [x] Include late-source warnings on closed periods, zero-effect PASS exclusion and private-detail protection.
- [x] Verify review/prepare/post/retry/deferred checks and both concurrent orders, rollback, migration replay, legacy close and empty-period behavior.
- [x] Expose aggregate blockers clearly to Management. Source details require current private authorization or stay omitted.

### Task6: Integrate and verify

- [ ] Review combined diffs and update compatibility tests without weakening behavior.
- [ ] Run full Portal, Flutter and backend commands plus bounded fresh-schema real-money/recovery validations. Report all actual failures/skips accurately.
- [ ] Run scoped static/security regression gates and independent standards/spec review.
- [ ] Save repair evidence, remaining business-readiness work and deployment/migration instructions. Commit the reviewed implementation.
