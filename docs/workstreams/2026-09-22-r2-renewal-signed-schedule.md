# Gap R2 - Renewal signed-schedule consistency

## Status and authority

Workstream setup only, 22 September 2026, following Management's approval of the first four Draft PR tracks in [audit #448](https://github.com/GILBIC/spina-lending-app/issues/448#issuecomment-5770984236). No renewal behavior is changed by this brief. The audit's static discrepancy has not yet been reproduced as a transaction failure.

Starting main: `6a33ab481574bf702920760610f803b59ffbd3ac`.
Starting tree: `1c88730791d89e2798faef0f5e76fd2a5f081543`.
Branch: `gap/r2-renewal-signed-schedule`. Coordination index: #448.
R2 is a gap-review identifier, not frozen Master #296 priority 2.

## Outcome and source boundary

Make renewal summaries consume the correct authoritative signed-schedule facts rather than reconstructing contractual totals from mutable product defaults. Preserve approved renewal thresholds and distinguish contractual maturity from current operational finish.

The reviewed `gilbic_backend/src/gilbic_backend/renewal_workflow_api.py` derives a contractual total from principal versus daily amount multiplied by the loan-type term, with a 120-day fallback. Its payload uses that value for paid percentage and the Regular 50-percent eligibility flag. Separate execution validation checks persisted cash/settlement evidence; the summary finding is not proof that journal or cash amounts were posted incorrectly.

Read existing contract-schedule, renewal-query, allocation and settlement authorities before selecting the source. Do not substitute principal-only percentages or silently change eligibility policy. Explicitly resolve historical loans without a registered schedule; missing authority must not be fabricated.

## Ownership and dependencies

Own the bounded backend renewal-summary query/projection and focused tests. R1 / PR #449 owns first-loan tax/document source binding. R6 owns staff request-money representation, including Android renewal models. R9 owns app-owned temporary photos.

Avoid changing Android money models in this branch; preserve the established API money representation or coordinate an explicit versioned contract adjustment with R6. Shared schedule helpers, SQL views or migration changes require a recorded ownership decision in #448 before editing. No migration identifier is allocated. Later R5 identity/liveness work must not independently rewrite this renewal API while R2 owns it.

## Next work

Trace existing authoritative totals and payment components, present a bounded correction design, then add regression tests that distinguish the signed contract from the product default. Reproduce the discrepancy before modifying production code. Scope the first correction to the renewal summary unless tests establish a separate defect.

## Acceptance checklist

- [ ] Verify the source and approve the bounded correction design.
- [ ] Prove a Regular/custom signed schedule that differs from daily amount times default term.
- [ ] Cover 7x7 agreed-payment duration without inventing a new eligibility threshold.
- [ ] Cover partial payments, voided/reversed transactions, paid loans and exact percentage boundaries using existing policies.
- [ ] Explicitly handle missing/historical schedule authority without invented totals or silent rewrite.
- [ ] Preserve cash/settlement validation, authorization, old signed history and API compatibility.
- [ ] Verify focused tests and required exact-head CI, then any affected cross-surface acceptance separately.

No R2 regression tests or production fix have been added/run at setup. No shared/live database, configuration, merge, deployment or financial operation is authorized.

## Resume protocol

Read this PR, #448, current Notion audit/checkpoint and Create State before editing. Work in an isolated checkout for this branch. Record exact head, owned files, dependencies, verified tests, outstanding evidence and next step. Red/Green refers only to the named checkpoint; code checks do not imply physical acceptance or merge permission.
