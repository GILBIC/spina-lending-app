# Gap R1 - Tax/disclosure source binding

## Status and authority

Workstream setup only, 22 September 2026. Management approved the first four Draft PR workstreams after the proposal in [audit #448](https://github.com/GILBIC/spina-lending-app/issues/448#issuecomment-5770984236). This brief is not completed implementation or an approved detailed tax/schema design.

Starting main: `6a33ab481574bf702920760610f803b59ffbd3ac`.
Starting tree: `1c88730791d89e2798faef0f5e76fd2a5f081543`.
Branch: `gap/r1-tax-disclosure-binding`. Coordination index: #448.
R1 is an audit gap identifier, not a renumbering of frozen Master #296.

## Outcome

Bind authorized precomputed loan/tax components from one approved source to the locked first-loan packet and its downstream consumers. Preserve the recorded DST-upfront/GRT-within-agreed-repayments direction without choosing rates, changing agreed installments, or manufacturing a source reference. Document rendering must not become a second pricing or accounting engine.

## Current source boundary

- `gilbic_backend/src/gilbic_backend/loan_document_tax_breakdown.py` projects supplied exact amounts. Its own contract says reference equality/arithmetic do not establish source ownership, provenance or legal applicability.
- `gilbic_backend/src/gilbic_backend/first_loan_terms.py` and `first_loan_documents.py` currently expose generic deductions and schedule totals; the audit identifies missing runtime binding of separate tax/source facts.
- `docs/forms-documents/2026-09-16/templates/T02-cash-loan-agreement-r4-tax-itemization.md` records the unimplemented source-binding boundary.
- Operational release is distinct from protected General Ledger posting; use #443's supported-product/deduction boundary rather than assuming every release is journal-ready.

These are source-review findings, not proof of a failed real transaction.

## Ownership and dependencies

Primary ownership is first-loan tax/approval/document binding and its focused backend tests. Read shared schedule/accounting authorities; do not alter them implicitly. R2 owns renewal summary authority, R6 owns staff request-money encoding, and R9 owns temporary-image lifecycle.

No shared SQL migration number is reserved by this brief. Record any necessary schema allocation centrally in #448 before creating a migration; recheck live main and other open branches. Coordinate any shared first-loan/schedule contract change before publication. Separate dependent document/accounting slices when the resulting diff would no longer be reviewable as one change.

## Next work

Trace the persisted authorized loan/tax source and its version/approval relationships, then present the narrow source-binding design. Identify unsupported Amount Financed/EIR inputs explicitly; never alias them to net cash. Write the required regression tests before production changes. A missing authoritative input stays blocked, not zero.

## Acceptance checklist

- [ ] Resolve the authorized source and approve the scoped implementation design.
- [ ] Reject wrong-loan, stale-version, unapproved, missing and conflicting source evidence.
- [ ] Reconcile each disclosed component exactly once across packet, net cash and unchanged agreed schedule; distinguish explicit zero from unresolved.
- [ ] Preserve historical signed packets and use a new approved version for changed terms.
- [ ] Prove the chosen product/deduction accounting path, without automatic journal posting or a duplicate calculator.
- [ ] Record exact-head focused tests and required CI; record actual document/device acceptance separately.

No feature tests have been added or run for R1 at setup. No product source, tax rate, live record, production setting, deployment, merge or release is changed by this brief.

## Resume protocol

Read this PR, #448, latest Notion audit/current-state checkpoint and Create State before editing. Use one isolated checkout for this branch. Record exact head, changed files, dependency state, evidence and next action after meaningful progress. Red/Green describes only the named checkpoint; it does not grant merge, deployment or financial-operation authority.
