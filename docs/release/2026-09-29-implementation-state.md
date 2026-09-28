# SPINA audit correction and supported-platform state

Checkpoint: 29 September 2026, Asia/Manila. [Issue 448](https://github.com/GILBIC/spina-lending-app/issues/448#issuecomment-5872009447) holds the current all-20 inventory and exact PR/CI/deployment evidence. [Issue 296](https://github.com/GILBIC/spina-lending-app/issues/296) remains the master roadmap. The [source audit](https://app.notion.com/p/3e95ade7bef481bfbd51d02b0aee153f) records the pre-fix findings and their reproductions.

## Supported surfaces

The owner requested retirement of the original standalone desktop and correction of the audit findings. The Python/Tkinter application, its independent account store, desktop-only tools/generated maps and obsolete self-hosted PR/push workflows are removed. Git history preserves their source. Existing business data, private files, backups and recovery artifacts are not deletion targets. Historical records still require authoritative reconciliation before any new financial use.

Web and Windows share `spina_portal/`; `spina_pc/` installs the portal in browser app mode. Android uses `gilbic_mobile/`. Shared iOS source is retained, while native iOS delivery remains outside V1. A small pure historical 7x7 allocator is retained exclusively as an independent test oracle; no current production package imports the retired desktop.

## Audit correction scope

| Finding | Correction / verification boundary |
|---|---|
| SEC-1 device approval | Preserve native-device provenance and pending approval across platform claims; Web-to-native Collector registration requires Management approval. Existing active devices with uncertain historical provenance need an operator review; source changes cannot manufacture historical approvals. |
| SEC-2/3 uploads | Bounded streaming rejects excess bytes before storage; synchronous identity/database/storage work runs outside the asynchronous event loop. Protected filename CORS support is explicit. |
| MW-1/2/3 sessions | Generation-bound native/Web requests cannot restore a logged-out or superseded session. Local logout clears access before bounded remote revocation. |
| B1 annual payroll | Count supported prior settlements once and reject ambiguous partially settled tax-bearing runs. Automatic annual reconciliation also stops for settled leave conversions without recorded taxable/exempt allocation; an explicit reviewed withholding amount and basis remains supported. No tax treatment is invented. |
| B2 history coverage | Reject opening-history/weekly overlap in either operation order; reject unsupported year-spanning aggregation. |
| B3 settled payroll | Paid zero-net records and settlement evidence remain immutable. Corrections use linked records. |
| Payroll history correction | Owner-only, versioned, idempotent supersession preserves original opening facts and invalidates stale calculations. |
| B4 close invariant | Migration `0130_guard_period_close_unfiltered_balances.sql` rejects nonzero inactive/nonposting temporary-account balances and checks the unfiltered close result. Production inspection found the prerequisite close definitions absent. Apply the reviewed, atomic `0091` / `0092` / `0130` / `0131` chain after catalog comparison; do not replay unrelated historical scripts. This installs definitions and permissions without posting financial records. |
| Journal reversal completion | Migration `0131_allow_reviewed_journal_reversal_post.sql` permits separately reviewed linked reversal drafts only after validating original identity, exact swapped lines and shared posting rules. Duplicate/reversal-of-reversal and generated draft shortcuts remain blocked. |
| MW-4/5 | Exact decimal-text money display and explicit Manila business times across staff/mobile views. |
| MW-6/8/9 | Private PDF proof selection, guarded Web refresh and native Collector residence-visit submission reuse existing protected contracts. |
| MW-7 | Web Management now exposes contract activation, No Collection preview/declaration/reversal, direct payment/void, manual journal/reversal, periods, formal close, opening/capital/measurement/outcome, tax evidence and tax/ECL actions through existing APIs. Separate preparation, exact review and posting remain enforced. |
| D1/D2 and O3 | Retired desktop login/recovery paths are no longer shipped. Persistent runners accept only explicit protected-main maintenance; normal PR checks run on hosted machines. |
| O1/O2 and delivery | Standard deployment preserves declared domains/origins, requires independently pinned SSH identity and protected environment inputs, installs a hash-locked runtime, verifies every declared HTTPS host according to its declared portal or API-only role and records the exact active source. Linux runtime verification is part of CI. |

Implementation in this branch and its focused regressions are not a production-delivery claim. The linked checkpoint records the final combined CI, independent review and exact deployed revision. Prior production was `f2b15fb193bdcb31d4e30f1e9bb4f8e658b37b50` with only targeted migration0129 applied. Do not reuse an earlier green result for this candidate.

## Verification before release

The initial fresh disposable database suite passed 815 tests; the isolated close suite passed 20. Subsequent focused reversal tests passed nine and payroll repository tests passed 15. The broad local Python run passed 3,034 tests and skipped 1,059 database/environment cases; seven obsolete workflow assertions were retired and six local Git-trust failures were resolved, with all 50 affected checks passing. Separate database results provide the financial coverage. The complete Web suite passed 826 tests and its build passed. Flutter analysis was clean; its complete local suite passed 913 tests with one Windows symlink-dependent skip.

The new management screens were rendered in a real browser at 1366px and 390px with synthetic read responses: all five panes, labels, overflow and nested accounting/tax/evidence navigation passed without page errors. This browser evidence does not claim real-account financial or physical-phone acceptance. Lint, format and type comparisons introduced no findings against the retained scanner baseline. Final exact-head CI and deployment evidence belongs in the linked continuity record.

## Remaining facts and acceptance

- Positive GRT/other-component calculation, split/rounding and accounting cases need accepted business inputs. Ordinary Regular/7x7 allocation and DST/GRT timing are already approved.
- GCash settlement and fresh CIF/liveness require actual accepted provider contracts. Screenshots, checkboxes and redirects cannot prove payment or identity.
- Office-renewal fallback is a blocked state, not a completed office-release workflow. The first-loan API rejects an existing borrower. Accepted office signer/document/cash evidence and a protected completion path remain needed; do not bypass the remote gate or reuse first-loan release.
- Owner/staff mapping, rates/schedules, company/privacy records, executable approved templates/converter and real credential email remain factual configuration gates.
- The installed Android main app uses an earlier CI debug identity. A permanent owner signer and data-preserving transition need a concrete plan; no compatible signer or unlocked-phone acceptance is assumed.
- Actual role/browser/Windows/phone, accessibility and interruption acceptance remain distinct from mocked/synthetic tests. No final iOS acceptance is claimed.
- The actual scoped database/private-file restore passed before this audit. Automatic off-site backups, retention, alerts and independent recovery-key custody remain unestablished. Cloud prices were explained; no paid destination was selected or activated.
- Representative authenticated performance and operating budgets still require evidence and acceptance.
- Business priorities13–17 require actual legal/opening/funding/loan/close records. Future priorities18–20 remain deferred.

Create State requires reconnection. GitHub, Notion and the local dated checkpoints retain continuation state. Do not repeat completed recovery or bulk migrations from older dated notes.
