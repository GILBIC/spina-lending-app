# Accounting completion execution ledger

Plan: docs/superpowers/plans/2026-10-05-accounting-completion.md

User authorized planning and fixes, then confirmed separate owner/corporate books. Baseline b5d6962; isolated branch codex/accounting-completion-20261005. Other Office checkout is untouched. Native worktree creation failed because the older chat repository lacks this commit; a worktree was created from the verified repository instead.

Ruling: use isolated databases/deployments for legally separate books. Existing functions and reports are single-book throughout; a partial book_id change would permit cross-book contamination. The cost is separate deployment/setup, rather than an unsafe selector.

Ruling: production configuration and accounting judgments are evidence inputs, not values inferred by an implementer. No deployment, actual balances or live migration is performed by this run.

Preflight interface check:

| Producer → consumer | Contract and finding |
|---|---|
| 0 → 6 | Preserve existing report fields; all new reports share the established snapshot. |
| 1 → 3/4/5/6 | One DB identity; context compatibility required before mapping or posting. |
| 2 → 3/4/5 | Initial source blockers are replaced only by exact reconciled adapter evidence. |
| 3 → 4/5/7 | Source identity, cash once, mapping version, idempotency and atomic posting audit. |
| 4 → 5/6/7 | Reconciled outstanding liability is valid; absence of payment is not a close failure. |
| 5 → 6/7 | Completeness digest is distinct from arithmetic balance. |
| 6 → 7 | Statements must reconcile across cash, equity and GL, including comparative data. |

## Implemented first controls

- Task0: repeatable-read/read-only statement snapshot, with book identity in that same snapshot. A real two-session RED reproduced100period earnings versus125cumulative earnings; the fixed test sees100throughout and125on the next request. API distinguishes arithmetic balance from source coverage and annual-package completion.
- Task1: migration0140 private immutable book setup, exact retry/evidence/current authority, corporate fresh-data guard (including zero-activity close history), context/wallet compatibility, book API, report/client labels. Optional `GILBIC_EXPECTED_ACCOUNTING_BOOK_ID` rejects the wrong database and returns unavailable readiness. Two synthetic databases prove application binding; deployed credential isolation remains an infrastructure check.
- Task2: migration0141 inventories authoritative Treasury/Collector facts, including sources without drafts; blocks review, preparation/retry and close under source locks; rechecks at commit; permits later actual-money evidence and flags closed history. Zero-effect PASS settlements are omitted; gross-positive settlements remain blocking even at zero net cash. Live queue and summary agree; Closed still lists periods with late warnings. Detailed source facts require current private wallet authority or are redacted. Valid unpaid amounts are not required to become zero.
- Portal and Flutter show identity, posted-ledger scope, partial coverage and exact/redacted source blockers; stale session/period responses are discarded. These labels do not claim full lending readiness.
- Added fresh-schema0141 verifier and CI step with explicit loopback/name/opt-in checks and zero skipped-test allowance. Older bounded verifiers remain.

Independent review found and repaired private-wallet detail disclosure, zero-effect settlement blocking, fresh corporate setup admitting empty close history, readiness returning500on wrong book pin, and closed-period list visibility. Tests also found and repaired the inherited blocked-filter literal-percent psycopg parameter bug. Initial reviewer was static; root ran the proof below.

Evidence directory: `../checkpoints/accounting-completion-20261005` relative to this checkout. `controls-reviewed.txt`:108passed, zero skips, one existing Starlette/httpx deprecation warning on fresh0141. `flutter-controls-reviewed.txt`:27passed. `portal-controls-final.txt`:50passed, zero skips. Scoped Ruff check/format:17initial control files clean. The final Python source rerun in `controls-final-source.txt` also passes108checks after annotation/format cleanup. Dart brace-only analyzer cleanup follows the27passing test run. RED outputs: `book-red.txt`, `snapshot-red.txt`, `guard-red.txt`, `source-api-red.txt`, `pin-red.txt`, `review-red.txt`. Earlier143baseline checks are distinct from these new-change proofs.

## Program continues — not lending-company-ready yet

User additionally said **“No need, you can do it”** when asked about framework/chart choices. `docs/accounting/lending-accounting-design-decisions.md` records the chosen lending design. Engineering proceeds without waiting for external policy approval; real entity/balance/tax facts are never manufactured.

- Task3:0142receipt adapter in progress. Initial SQL13tests pass (`receipt-initial.txt`); API/repository/integration, application, payout, transfer and correction families remain.
- Task4: liability control schedule SQL144 and API/repository implemented. Initial23PostgreSQL checks pass; expanded31checks and17API checks await root rerun. No claimed liability balances are seeded. Two-connection races, route/UI and close integration remain.
- Task5:0143initial legacy collection/release/remittance source tests9pass (`legacy-initial.txt`); dated EIR/ECL/tax coverage and integration still in progress. `adapters-red.txt` reproduced missing raw-source guards.
- Task6: full cash-flow/equity/comparatives/notes package remains; current two-statement pack is explicitly incomplete.
- Task7: composed latest-schema money cycle, concurrency/recovery, final client/full CI and rollout evidence remain. No live database, deployment or real-money action has occurred.

Final initial-client analyzer proof: `flutter-analyze-final.txt` reports no issues in8scoped files. Additional adapter RED (`adapter-extra-red.txt`) proves a missing unallocated receivable assessment blocker and erasable receipt proof via TRUNCATE; the matched unpaid-liability case passes. These are repaired within the next adapter increment, not counted in the first control commit.
