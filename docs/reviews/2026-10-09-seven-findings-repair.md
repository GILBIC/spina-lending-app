# Seven confirmed review findings: repair record

Date: 2026-10-09. Baseline: `f11a01ad6839a0e03a2149fc386cd50ba2267490` on `codex/review-fixes-20261006`.

This repair addresses the seven confirmed findings recovered in the conversation review. It does not assert an exhaustive review of every conversation or every product behavior.

| Finding | Result | Regression evidence |
| --- | --- | --- |
| O1: separation leave could be spent again during partial payout | Approved and partially paid separation snapshots reserve their conversion minutes. Settlement excludes its own reservation before checking the remaining entitlement. The final payment creates the single leave debit. | Competing ordinary leave/conversion is blocked; reprepare and inactive snapshots behave correctly; real PostgreSQL partial/final payment and replay remain atomic. |
| O2: future attendance became payable merely as time advanced | Validation compares captured time with the immutable server receipt time as well as current time. An approved correction can resolve the anomaly. | Clock advance alone still blocks payroll; correction approval permits the verified shift; delayed out-of-order offline events can still complete a valid chain. |
| O3: leaving native Other Area discarded an uncertain payment identity | Module departure is blocked while a payment is unconfirmed. A visible retry action retains the original client and exact draft even when search results change. | Timeout, editor Back, module Back and retry preserve the request; authority denial clears private data and permits departure. No new persistent payment queue was introduced. |
| O4: an old attendance denial revoked renewed access | The durable revocation update checks its authorization epoch inside the vault transaction. | Old 401, 403 and 426 responses cannot revoke renewed authorization; the service can retry the retained attendance command using the new session. |
| O5: Web Other Area retained private data after denial | Active 401/403/426 responses dispose the module, clear its display and invalidate callbacks. | Both Collector and Management views clear borrower/forms; detached controls cannot submit; late remittance responses cannot repopulate data; transient 503 retains drafts and permits search retry. |
| O6: native opening workbook rounded large cents | Proposed debit/credit amounts remain normalized decimal strings through parsing, prefill, review, model and HTTP body. | `1000000000000000.01`, maximum `9999999999999999.99`, ordinary cents and zero round-trip exactly; invalid range/precision and canceled review cannot submit. |
| O7: tax credit/refund evidence could race | Additive migration 0142 installs a shared per-adjustment transaction lock and opposite-evidence check at both INSERT boundaries. | Real lock waits are observed in both ordering directions; the loser rejects after commit and can proceed after rollback; exact retries, protected posting and audit rollback remain valid. |

## Database delivery

Apply `gilbic_backend/sql/0142_serialize_v1_tax_recoverable_realization.sql` to enable O7. It installs both guards atomically after existing evidence writers finish. New evidence writes require READ COMMITTED so the post-wait check sees the competing commit. Existing protected owners, authorization, derived amounts, immutability and posting rules remain in place.

The migration does not rewrite existing evidence or choose a winner for historical collisions. Its apply and reapply checks preserved evidence, journal and audit counts. The observed defect was conflicting evidence; neither the review nor this repair claims that both financial postings occurred.

Only isolated local synthetic databases were used. The repair did not deploy an application or migration to production.

## Evidence location

Detailed red/green logs, domain reports, test manifests and harnesses are retained in `C:/Users/pc/OneDrive/Documents/ChatGPT/Gilbic/artifacts/seven-fixes-20261009/`. Key reports are `employee-report.md`, `android-report.md` and `tax-report.md`.

## Validation

- Web: all 1,988 tests passed; syntax checks passed for 287 modules.
- Employee: 94 focused unit/API/domain tests passed, plus 42 real PostgreSQL tests. After test-only UTC import cleanup, the 12 new unit and 2 new PostgreSQL acceptance tests passed again.
- Tax: all 16 tests passed on a fresh schema replayed through 0142, including both race orders, rollback/replay and complete current-schema credit/refund lifecycle checks. The reusable runner dropped only its generated database.
- Native focused checks: 52 tests passed, followed by 13 navigation tests after the final page refactor. Flutter analysis completed without issues.
- Changed Python files add no Ruff findings; two pre-existing findings remain. Pyright baseline comparison adds no diagnostics: the same 411 errors and 5 warnings exist before and after these changes.
- The owned PostgreSQL test cluster was stopped after validation. Test data and logs remain available as evidence.

- Python whole-suite collection: 5,077 tests; reconciled results are 3,560 passed and 1,517 skipped, with no unresolved failures. The raw parallel run was not green: it had 269 setup errors after three OS Temp base directories disappeared (removal cause unproven), 37 missing Annex-template failures and one shell lifecycle timeout. Explicit template/renderer fixtures and isolated reruns resolved these cases. Logs retain the raw run as well as 44 Annex, 18 tax PDF, 62 affected-module and 103 additional passing rerun results; 120 additional cases correctly skipped once fixture setup worked. Database tests skipped by the broad run are not claimed as executed; the separate 42 employee and 16 tax PostgreSQL checks above are the relevant database evidence.
- Pytest retained its existing plugin-rewrite and Starlette/httpx deprecation warnings. Local synthetic PDF revision metadata is a test fixture, not a GitHub CI attestation.
- Final collection contains 5,083 tests. The six additional cases are current-schema tax lifecycle checks, all included in the fresh 16-test PostgreSQL run. Nine existing disclosure-route case IDs contain a newly generated UUID at collection time; their source is unchanged.

- Flutter whole suite: 1,571 passed, 1 skipped, zero failures with the pinned Flutter 3.44.7 runtime (`flutter test --no-pub --concurrency=2 --reporter=expanded`). No device or release build is claimed.
