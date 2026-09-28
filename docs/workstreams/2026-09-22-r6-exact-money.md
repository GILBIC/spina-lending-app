# Gap R6 - Exact money on staff request paths

## Status and authority

Implemented 28 September 2026, following Management's authorization to complete the remaining work. Review remains tracked in [audit #448](https://github.com/GILBIC/spina-lending-app/issues/448).

Starting main: `6a33ab481574bf702920760610f803b59ffbd3ac`.
Starting tree: `1c88730791d89e2798faef0f5e76fd2a5f081543`.
Branch: `gap/r6-exact-money`. Coordination index: #448.
R6 is an audit identifier, not frozen Master #296 priority 6.

## Outcome and evidence

Preserve authoritative decimal amounts when staff enter, review and submit payments or renewal amounts. Reuse exact decimal-text/minor-unit patterns already present in the project; do not add a new money framework or change the server allocator.

The reviewed `spina_portal/assets/collector-contract.js` normalizes money through Number and toFixed. The audit's isolated copied-function probe preserved 100.01 but changed 1000000000000000.01 to 1000000000000000.00. This is a boundary finding, not proof ordinary microloan balances are wrong or that such a large amount is an approved product value.

Some Android staff models, including `gilbic_mobile/lib/src/core/payments/combined_payment_submission.dart` and `gilbic_mobile/lib/src/core/renewals/collector_renewal_workflow.dart`, use double-based money parsing. Trace each value to its serializer before classifying display-only conversion as an authoritative write defect.

## Ownership and dependencies

Own Web request-money normalization and directly affected form values/tests, then Android staff money models/serializers and directly affected tests. Preserve API field names and approved money semantics.

R2 / PR #450 owns the backend renewal-summary query and business interpretation; coordinate any response-contract change rather than editing that API here. R1 / PR #449 owns tax/first-loan/document sources. R9 owns photo lifecycle, not financial forms generally. Future R3 Collector Web actions should consume the relevant R6 result before editing the same contract/form files.

Keep the first code slice Web-only if that is the smallest verifiable change; continue Android as a separate reviewed slice or split the PR if review size requires it. Do not claim the entire R6 gap closed after only Web completion. No SQL migration, allocator or broad unrelated formatting change is planned.

## Implementation and verification

Web collection and promise amounts now retain decimal text through normalization and submission; form defaults preserve the original server digits. The existing numeric(18,2) input capacity permits 16 whole digits, so larger text input and fractional cents are rejected. Legacy numeric inputs at or above 2^46 are rejected because adjacent cents cannot all be represented there.

Android payment, promise, correction and Management renewal terms serialize decimal strings. Route cache round trips and editable defaults preserve authoritative strings. Combined payment totals use the existing journal minor-unit helpers, and automatic acceptance compares exact preview amounts. Existing display-only doubles remain; no allocator, schema or product limits changed. Correction and renewal APIs already accept Decimal fields.

Verification: `npm test` passed 704 tests and module syntax checks; the full `flutter test --no-pub` suite passed 836 tests. Regression tests reproduce the former Web default and Android entered-amount precision loss, cover maximum supported cents and invalid inputs, and preserve retry/idempotency behavior. Local Flutter analysis did not complete because its SDK-cache permission request was interrupted; remote CI analysis remains required before integration. Evidence logs are in the parent workspace `checkpoints/r6-portal-tests.txt` and `checkpoints/r6-flutter-tests.txt`.

R2's nullable contractual-total/paid-percent changes remain independent. R3 can import exported `normalizeMoney` for its new Web workflows. No production transaction, migration or deployment was performed.

## Original design scope

Trace current backend amount limits, rounding policy and exact helper behavior. Present the narrow Web normalization design and reproduce the precision boundary with a test of the actual imported builder, not a copied helper. Define reject/preserve behavior using existing supported limits before changing production code; an out-of-range value should fail rather than round silently.

## Acceptance checklist

- [ ] Confirm the bounded design and the actual supported request limits.
- [ ] Add failing tests against real production imports for ordinary cents and the high-precision boundary.
- [ ] Cover zero/negative/blank/invalid values, more than two fractional digits, separators, exponent syntax and boundary overflow according to the existing request contract.
- [ ] Preserve stable idempotency identities, allocation intent and authorized server request shape.
- [ ] Keep exact values through Android parse/display/edit/serialize where they can reach a write; separate percentages and non-money measurements.
- [ ] Verify focused Web/Android tests and required exact-head CI; reconcile any R2/R3 dependency before integration.

The remaining integration gate is remote CI on the published R6 head plus reconciliation with R2/R3.

## Resume protocol

Read this PR, #448, latest Notion audit/checkpoint and Create State. Use an isolated checkout and one active owner. Record exact head, touched paths, dependencies, actual test outcomes and next action. Red/Green applies only to the stated checkpoint; baseline Green is not feature completion or merge permission.
