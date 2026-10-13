# Full audit repairs — 9 October 2026

This repair batch addresses the 14 groups in the consolidated audit of source
`70670cb789ee283d73d113727a963a17df11c68e`. The user approved implementation after
the discovery pass. Changes are local; no production data repair or deployment
is included.

## Repair coverage

| Audit ID | Resulting behavior |
| --- | --- |
| S1 | Audited native views clear their private models and controls after explicit authority denial. Late asynchronous results cannot restore the denied view or start another protected action. Shared HTTP 401/426 failures propagate through proof children; object-scoped HTTP 403 remains local where appropriate. Transient failures retain retry behavior. |
| S2 | Management overdue rows use the database decision based on the same date as summary counts and sorting. |
| S3 | An uncertain detailed collection keeps its immutable command identity through Back/reopen and retries in both Daily Route and Other Area entry. Pending ownership is bound to the Client and loan; starting another entry cannot discard that pending attempt. |
| S4 | Native combined-payment acknowledgment must match the submitted command and reviewed payment components. Invalid or malformed successful responses remain uncertain. |
| F1 | Authentication rate limits, outages and temporary conflicts stay retryable. They no longer become credential-rejection responses that delete a valid session. |
| F2 | A photo child's HTTP 401/426 invalidates the owning notification view. Object-scoped HTTP 403 remains local to the photo. |
| F3 | A legacy receipt correction cannot mark an incompletely paid day covered. Corrections requiring a new Past Due reason are rejected before mutation; the tested recovery path uses Undo and normal replacement posting. |
| F4 | Legacy Regular applied receipts update linked Past Due obligations and promises, with repeat reconciliation avoiding double application. Both capture and reconciliation cap the unpaid amount at remaining debt, so final payoff closes the linked obligation. |
| F5 | Leave conversion preparation, approval and completed payout verify currently eligible unused credits. Future or stale entitlement cannot authorize settlement. |
| F6 | Weekly payroll preparation, approval and payout stop while a disbursed advance's revised terms await review, including previously prepared snapshots. |
| F7 | Exact document-review replay preserves the promoted Client identity. Changed requirements and historically inconsistent promoted states return a conflict before duplicate Client creation. |
| F8 | Client paid amounts come from nonvoid applied receipts, including interest, independently of principal-minus-balance arithmetic. |
| F9 | Treasury reverses a supported three-component application through a verified same-loan receipt chain, preserving stale-state rejection and atomic rollback. |
| F10 | Management cannot void receipts with linked Past Due/promise changes until a protected correction can restore every linked record. |

F3, F6, F7 and F10 deliberately reject unsafe transitions instead of inventing
missing borrower reasons, approvals or historical state. Existing inconsistent
production records are not silently rewritten.

## Verification

Implementation uses failing behavioral regressions followed by passing controls.
Financial and projection acceptance tests run against a new loopback PostgreSQL
18 cluster with synthetic data and schema migrations through 0141. The runner
restricts connections to the disposable database. Unit/API runners disable
dotenv and external database/network access.

Confirmed checks:

- Portal syntax: 286 modules.
- Portal suite: 1,978 passed.
- Auth provider/API/client selection: 73 passed.
- Client and Management projection unit/API selections: 22 passed.
- PostgreSQL projection selection: 21 passed.
- Employee/onboarding selection: 124 passed, 31 database skips.
- Financial affected-unit selection: 249 passed, 14 database skips.
- Final financial/journal PostgreSQL selection: 80 passed, zero skips. This
  includes all 77 financial cases, the unchanged source-preview case and both
  original posted-journal reversal/atomic-rollback cases after the final source
  change.
- Supplementary accounting verification: ten checks passed, comprising seven
  current-schema/authority-compatibility checks, one current-schema
  extra-principal reversal and two historical posting cases at migration 0066.
- Onboarding PostgreSQL selection: 16 passed, including eight new identity,
  uniqueness, HTTP conflict and row-lock cases.
- Full Python discovery: 5,053 cases. The initial 5,041-case execution had
  3,509 passes, 1,493 environment-gated skips and 39 PDF proof setup failures.
  All 39 setup failures passed after configuring the existing original template
  and pinned LibreOffice 26.2.5.2: 44 Annex cases and 18 tax-document cases passed.
  The original collection therefore reconciles to 3,548 passes and 1,493 skips.
  The twelve subsequently added financial/onboarding cases passed in the focused
  PostgreSQL runs. A corrected draft-loan fixture also passed there.

The PDF proof run used an explicitly labeled local revision fixture, not a
GitHub event or CI attestation. LibreOffice rendered in a short local temporary
directory after the first attempt stalled under a long OneDrive path. Only the
verified task-owned stalled processes were stopped.

Supplemental 7x7 verification corrected a stale shared test fixture. It now uses
the current signed amortizing schedule when that authority is installed, while
preserving the historical stage verifiers' balloon schedule. Both authority
controls pass; no production accounting SQL or readiness protection changed.
Repeated synthetic runs had also accumulated records that violated an older
preview test's empty-database assumption. Its unchanged assertions pass on a
fresh schema through migration 0141. The supplemental runs use separate fresh
loopback databases and disable JIT only in their guarded test connections.
The historical posting test's pre-reversal assertion is intentionally specific
to migration 0066. Running it on 0141 initially produced the later controlled
reversal guard instead. Both original posting tests pass unchanged at their
intended 0066 stage; the current-schema reversal tests also pass unchanged.

Pyright 1.1.414, with explicit local package roots, reports the same 411 errors
and five warnings on the pinned source and the repaired source: no added
diagnostics. The newly introduced aggregate-row diagnostic was resolved with
an explicit invariant check. This is a regression comparison, not a claim that
the repository's inherited type-check debt is clean.
Ruff comparison across the 27 changed Python files adds no diagnostics; 78
diagnostics are inherited from the pinned source. No broad formatting cleanup
was included in this behavioral repair.

Final Flutter analysis reports no issues. The 62-case follow-up selection and
the final 22-case proof file both pass, including the completed-download race
before a widget rebuild. The final complete Flutter suite passes **1,545 tests,
with one skip and zero failures**. The skipped symbolic-link safety case requires
symlink creation unavailable on this Windows host; it was not exercised here.
All 57 changed native files match the final tested SHA256 manifest.
Independent Standards and Spec reviews each report no
open actionable findings in this 14-group repair scope; their source judgments
are separate from the controller's executed test evidence.

All required repair checks and the supplementary verification described above
are complete. Database-required cases skipped in the general suite are
reported separately from the focused PostgreSQL acceptance runs. Overlapping
selections are not added together as a unique-test total.

## Scope and limits

No deployed acceptance, physical-device lifecycle test, provider settlement,
SMTP delivery, or customer-data operation was performed. The audit's separate
media-renderability and extreme-money-value follow-ups are outside this
14-group repair batch. Existing lint warnings are compared with the pinned
source so new diagnostics can be distinguished from inherited style debt.

Detailed red/green logs and test manifests are retained in the local task artifact
folder `full-audit-fixes-20261009`, outside the repository.
