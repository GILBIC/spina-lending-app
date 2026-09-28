# Gap R2 - Renewal signed-schedule consistency

## Status and authority

Implemented locally on 28 September 2026 under Management's instruction to complete the priorities. PR #450 remains the delivery track, following the original first-four-track approval in [audit #448](https://github.com/GILBIC/spina-lending-app/issues/448#issuecomment-5770984236). Review and exact-head CI are still required before release.

Disposable PostgreSQL reproduced the summary defect: a verified 7x7 schedule totaling 3,630.00 was reported as 14,520.00 from daily payment times the mutable 120-day product default. An unregistered historical Regular loan incorrectly received an invented 6,000.00 denominator. These are summary/eligibility findings, not evidence of incorrect journal posting.

Starting main: `6a33ab481574bf702920760610f803b59ffbd3ac`.
Starting tree: `1c88730791d89e2798faef0f5e76fd2a5f081543`.
Branch: `gap/r2-renewal-signed-schedule`. Coordination index: #448.
R2 is a gap-review identifier, not frozen Master #296 priority 2.

## Outcome and source boundary

Make renewal summaries consume the correct authoritative signed-schedule facts rather than reconstructing contractual totals from mutable product defaults. Preserve approved renewal thresholds and distinguish contractual maturity from current operational finish.

The portal, request submission and workflow summary now sum immutable contractual installment amounts from the active schedule joined to its verified registration. They do not use operational finish projections or product duration defaults. The Regular threshold uses the unrounded ratio; paid percentage is rounded only for display. Cash totals, authorization, duplicate-request protection, settlement validation, and the existing fully-paid/7x7 exceptions retain their policy.

For missing/unverified schedules, contractual total and paid percentage are explicitly null. Active Regular self-service requests cannot pass the normal 50-percent gate without this authority. Fully paid Regular and 7x7 loans keep their existing eligibility exceptions without inventing a denominator. Audit percentage is also null when unavailable. No historical schedules are backfilled or rewritten.

## Ownership and dependencies

Own the bounded backend renewal summary/submission consistency and focused tests. R1 / PR #449 owns first-loan tax/document source binding. R6 owns staff request-money representation. R9 owns app-owned temporary photos.

R2/R6 ownership was coordinated on 28 September: R2 makes only contractual total/paid percentage nullable in the two Flutter renewal models and renders unavailable evidence in Client, Collector and Management screens. R6 owns exact request amounts and serializers. Web now displays server-provided signed totals and eligibility messages, including unavailable evidence. Known totals remain decimal strings on the API; backend and clients must ship together for the null case. No shared schedule helper, SQL view or migration was changed. Later R5 identity/liveness work must not independently rewrite this renewal API while R2 owns it.

## Next work

Review and publish the branch, run exact-head CI, then record coordinated Web/Android acceptance. The request-submission denominator was corrected alongside the summary because leaving it on product defaults would disagree with the displayed eligibility. No accounting or release-execution behavior was changed.

## Acceptance checklist

- [x] Verify the source and implement the bounded correction under Management's completion instruction.
- [x] Prove a Regular/custom signed schedule that differs from daily amount times default term.
- [x] Cover 7x7 agreed-payment duration without inventing a new eligibility threshold.
- [x] Cover partial payments, voided transactions, paid loans and exact percentage boundaries using existing policies.
- [x] Explicitly handle missing/historical schedule authority without invented totals or silent rewrite.
- [x] Preserve cash/settlement validation, authorization and old signed history; update clients for nullable authority.
- [ ] Verify focused tests and required exact-head CI, then any affected cross-surface acceptance separately.

Local verification on 28 September: 27 focused backend tests; 63 disposable PostgreSQL tests (19 Area Management and 44 combined collection/renewal/7x7 tests including the five R2 database regressions); 13 Flutter renewal tests; 9 Web renewal tests. Flutter analysis of all changed models, screens and tests found no issues. New Python tests pass Ruff and formatting; touched Python files add no Ruff findings against the retained scanner baseline. All database evidence used an isolated localhost PostgreSQL cluster. No production configuration, deployment, financial operation or schema migration was performed. Local green does not establish physical-device acceptance or production readiness.

## Resume protocol

Read this PR, #448, current Notion audit/checkpoint and Create State before editing. Work in an isolated checkout for this branch. Record exact head, owned files, dependencies, verified tests, outstanding evidence and next step. Red/Green refers only to the named checkpoint; code checks do not imply physical acceptance or merge permission.
