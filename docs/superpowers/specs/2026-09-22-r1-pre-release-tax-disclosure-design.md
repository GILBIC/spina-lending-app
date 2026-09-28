# R1 - Pre-release tax/disclosure source contract

Date: 22 September 2026 (Asia/Manila).
Owner: PR #449, branch `gap/r1-tax-disclosure-binding`; coordination index #448.
Inspected source: `17591f4b87f38c6be70f24c0e64e225753108e17`, based on main `6a33ab481574bf702920760610f803b59ffbd3ac`.

**Approval status:** Management replied **Approve** to the three-part R1 design direction: approved disclosure before signing, the same locked information through documents/release, and separate actual-event tax accounting afterward. This written specification records the resulting detailed contract for review. It is not yet an approved implementation plan, implemented feature, executed test report, legal clearance, or merge/deployment authorization. The earlier workstream brief is historical setup context; this specification is the next R1 design artifact.

## 1. Outcome and scope

A borrower must review documents whose principal, itemized deductions, net cash and scheduled repayment components all come from one authorized, versioned source. A renderer must never invent a tax amount or retrieve whichever rule happens to be newest when a historical document is opened.

Extend the existing first-loan approval workflow, not the loan engine or General Ledger. Preserve the recorded DST-upfront/GRT-within-agreed-repayments direction only where an actual approved borrower-charge basis and supported component treatment exist. This specification selects no tax rate, gross-up method, exemption, charge entitlement or new fee.

The initial implementation slice is the pre-release source record and its binding into the existing approval packet. Full R1 completion additionally requires supported schedule/component, document, cash-release and protected accounting reconciliation. Finishing the first slice does not complete all of R1.

## 2. Existing authorities and the timing boundary

- `first_loan_api.ApprovalRequest` currently accepts an application version, terms, template version and request UUID; it checks canonical office/Management roles and active device permissions.
- `first_loan_repository.approve` resolves the current application/CIF, generates the existing authoritative schedule, and atomically saves a loan approval and immutable packet/digest with approving actor/device. Its loan and packet IDs are created during approval.
- `first_loan_terms` owns the current schedule inputs and exact money types. Regular currently uses principal plus contractual interest; the schedule payload exposes principal and interest components, not a separate GRT-recovery component.
- `loan_document_tax_breakdown` reconciles supplied exact components. It deliberately does not establish provenance, tax applicability, borrower-charge authority or calculate tax/gross-up.
- A6.2 `accounting.v1_tax_rule_evidence` is reusable immutable rule evidence. Actual DST evidence requires a matching disbursement; percentage-tax evidence requires a matching collection. Those event records must not be created to make a pre-signing document appear ready.

Source links at the inspected commit are listed in section 12. These are source observations, not results from new executable tests.

## 3. Minimal architecture

Introduce one small private, append-only pre-release calculation register, proposed as `lending.first_loan_disclosure_calculations`. It stores reviewed calculation support and exact source bindings, not official balances, tax liabilities, payments or journals. A pre-release record binds to the existing application version and CIF; it does not require a loan/disbursement ID that does not yet exist.

The proposed operations remain inside the existing first-loan API/repository boundary:

- Record/review a calculation using the canonical Management role, an active approved device and existing `lending.first_loan.approve` permission. Creation of tax-rule evidence still uses its existing separate permission and workflow.
- Read the saved calculation through authorized office access. Calculation source files remain Management-only; office users receive only the required reviewed amounts and readiness explanation.
- Extend approval with `disclosure_calculation_id` and `expected_disclosure_digest`. Resolve the record on the server; never accept an arbitrary caller-supplied final packet or approved-actor flag.
- Copy the validated public financial snapshot into proposed packet schema version 2 under `tax_disclosure`, covered by the existing packet digest. Keep internal support manifests out of borrower-facing payloads and rendered originals.

Use existing private evidence storage and hash/size validation for retained support. New evidence-purpose bindings or a small guarded relationship may be required; they must be explicit in the implementation plan. Do not upload arbitrary paths, fetch arbitrary caller URLs, expose private storage keys, or treat a reference plus hash as proof of ownership. No new background job, public application route, provider integration or parallel approval system is needed.

No SQL migration number is reserved here. Allocate any forward migration centrally in #448 after checking other workstreams; never modify an already-applied historical migration.

## 4. Versioned record contract

All fields below are proposed contract fields, not claims that they already exist. Store money as exact currency-cent decimals and transport it as decimal strings; use the existing 18-digit/2-decimal boundary. Reject booleans, floats, non-finite values, negatives, overflow and unsupported fractional cents where a money value is required. Rates retain their owning rule precision rather than being treated as money.

| Group | Required meaning |
| --- | --- |
| Identity | Server-issued calculation UUID, schema version, application-scoped version, immutable request UUID, optional explicit superseded calculation ID. |
| Source owner | Server-resolved client, current application version and current CIF version; not names or matching email as identity. |
| Economic binding | Canonical proposed terms and authoritative schedule fingerprints, product, currency, planned release/date basis, first due date and signed-schedule maturity basis. Fingerprints use the existing canonical digest conventions and exclude their own digest fields. |
| Rule authority | Exact existing rule IDs, versions, effective-date scope and evidence digests/snapshots for the relevant tax treatment. Resolve applicability/supersession on the server; a caller cannot pick an unrelated rule merely because its amount reconciles. |
| Calculation support | Protected retained source identity, exact file digest/size/type where applicable, calculation method/version, reviewed inputs/output and substantive review rationale. The initial supported mode is explicitly identified as reviewed precomputed support, not automated tax-computation proof. |
| Borrower-charge basis | Separate reviewed authority for each amount passed to the borrower and its timing. Company tax-rule evidence alone is insufficient. A company-borne amount must not be presented as a borrower deduction or exemption. |
| Money components | Principal, contractual interest excluding separately classified GRT recovery, borrower DST upfront, scheduled GRT recovery, itemized other upfront/scheduled amounts, total deductions, net cash and total scheduled payable. Every item has a stable identity and reviewed classification; no catch-all residual is allowed. |
| Disclosure-specific values | Amount Financed, finance/non-finance charge classification and any required EIR with their own retained authorized method/basis. Missing or unsupported values remain unavailable; Amount Financed is not inferred from net cash. |
| Review audit | Server-recorded reviewing actor, persisted device and database timestamp, plus the canonical reviewed-record digest. Payload fields cannot impersonate these values. |

A first-loan record requires renewal offset to be explicitly zero; actual renewal-offset support belongs to the renewal workflow, not this slice. A valid zero borrower charge requires its recorded reason/support; zero does not automatically mean the company's tax due is zero or exempt.

A record can be **reviewed** but not **usable for approval/issuance**. Readiness is derived from source freshness, supported calculation/component semantics, required disclosure fields and the existing product/template guards. Do not persist a client-controlled `ready=true` shortcut. Unsupported cases return a specific blocker instead of silently omitting a component.

## 5. Exact reconciliation and component readiness

Run the existing document projection only after source authorization and classification checks. Reconcile these identities without inventing rates or new rounding:

- Upfront deductions = borrower DST upfront + separately approved other upfront items. First-loan renewal offset is zero.
- Net cash = principal - upfront deductions, and must match the existing cash-authorization basis.
- Scheduled payable = principal + contractual interest + scheduled GRT recovery + approved other scheduled items.
- Scheduled payable must also equal the sum of the exact authoritative installment amounts. Every component is counted once.

DST must map once to its existing deduction item; adding a display line must not create another deduction. GRT recovery must not be put upfront or added on top of agreed installments. Detect duplicate identities/classifications, not just repeated labels. Every nonzero other item requires an already supported approved source; this work authorizes no new fee category.

The current schedule has principal/interest components only. Positive separate GRT or another scheduled component cannot be enabled by relabeling existing interest or by calculating a leftover. If its authoritative split is not supported, retain reviewed evidence but return **component integration required** and block approval/issuance for that case. Extending the owning component model is a separately coordinated dependent slice. Tests of zero/compatible components alone must not be described as full tax-bearing loan acceptance.

Neither a shorter net cash amount nor a displayed tax estimate proves that the selected disbursement has a supported journal path. Preserve #443's explicit product/deduction accounting acceptance requirement.

## 6. Recording, approval and lifecycle

1. Load the current confirmed application/CIF using existing guards. Generate the schedule from existing approved engines and normalize the same proposed terms. Validate and retain calculation support under exact application/CIF/terms ownership. Record the reviewed version and its audit together; no actual-event tax/financial rows are created.
2. When approving, resolve the selected calculation and compare its digest and full binding with the current server source. Recheck rule dates, supersession, borrower-charge basis, component readiness, product/pricing and required document inputs. Copy only the accepted snapshot into the locked packet and bind it to the newly issued loan/packet IDs within the approval transaction.
3. Generation, signing evidence and cash authorization require that exact packet, calculation identity and digest. Recheck current readiness before a new signing/release action. The document renderer reads saved values rather than recalculating them. Required missing fields block issuance.
4. A changed application, CIF binding, economic term, relevant rule/date basis or calculation requires a new explicitly linked reviewed version and, where an approval exists, the existing cancel/reapprove and re-sign flow. Do not silently edit the approved packet, reuse its signatures or auto-approve changed terms.
5. After actual release, preserve the issued snapshot and original document bytes. Actual DST/receipt evidence and protected journal preparation/posting continue through their existing event-specific workflows. Reconcile differences explicitly; never rewrite the original disclosure to match later accounting or manufacture actual events to satisfy a pre-release dependency.

New pre-release review is not a new borrower signature step. The borrower still acknowledges/signs through the existing office process. Management's calculation review is not itself borrower consent or proof of cash receipt.

## 7. Replay, concurrency and failure behavior

Use stable request identities for source recording and approval. Identical authorized retries return the same saved IDs and bytes; changed payload/source reuse fails without a second approval, review event or disbursement. Authorized readback of an already committed result must not repeat side effects, even when current readiness has changed; a new downstream action still rechecks current guards.

Serialize version selection, source consumption and supersession under a consistent application/client/rule lock order. The implementation must demonstrate that a concurrent applicable rule update or calculation supersession cannot slip between validation and approval/release. Merely locking the old rule row is not proof that insertion of a newer rule was prevented. Coordinate any required rule-writer guard with the owning accounting code before changing it.

Validation or audit failure rolls back the complete database transition. Private-file staging follows existing immutable-storage recovery conventions: never delete committed/shared evidence during rollback, and distinguish an unreferenced staged file from an issued original. An uncertain response triggers same-request readback, not a fresh financial request.

Return permission failures through existing 403 handling, invalid input through existing validation handling and stale/unsupported source conflicts through the existing 409 mechanism with `Cache-Control: no-store`. Use safe explanations without exposing another client's identifiers or private source details.

## 8. Compatibility and rollout boundary

Read existing schema-version-1 packets and retain access to their released immutable originals. Do not backfill historical zero taxes, rewrite hashes or regenerate old signed packets using new templates.

When the new source-binding capability is activated, a new approval must include its calculation identity/digest; an old client that omits them receives an explicit update/source-required response, not silent bypass. Previously approved but unreleased schema-1 packets require controlled re-review/reapproval before new issuance/release under the new contract. Do not automatically cancel them. A replay of a previously completed release remains a read of its original outcome, not a new release.

Coordinate backend, Web, Android and Windows/shared-Web consumers before activation. Keeping incomplete component support blocked is a safety gate, not proof of full R1 completion. Production capability activation, migrations, template approval and deployment are separate authorized operations.

## 9. Regression specification - not yet executed

| ID | Required synthetic proof |
| --- | --- |
| R1-01 | A supported reviewed pre-release calculation can be recorded without a disbursement or collection. All actual tax-evidence, payment, disbursement, credential-intent and journal tables remain unchanged during this recording step. |
| R1-02 | Foreign client/application/CIF, changed terms/schedule, altered date basis and tampered digest are rejected before approval. |
| R1-03 | Inactive account, wrong role, missing exact permission, revoked device and spoofed review actor are rejected. |
| R1-04 | Missing, wrong-type, out-of-date or superseded rules block; company tax evidence alone cannot authorize a borrower charge. |
| R1-05 | Missing/corrupt/unbound retained calculation evidence fails; a fabricated string or correctly shaped hash cannot replace it. |
| R1-06 | Explicit supported zero succeeds where valid; missing, unsupported, company-borne and exempt meanings remain distinct. |
| R1-07 | Fractional-cent, floating-point, boolean, negative, overflow and non-finite inputs fail. Canonical exact-money round trips preserve all supported digits. |
| R1-08 | Every approved component reconciles once to deductions, cash and installment totals. Duplicate charge identities, DST counted twice and GRT upfront fail. |
| R1-09 | Unsupported positive scheduled GRT/other splits block without increasing installment amounts, extending term or relabeling interest. Compatible zero cases cannot mark this positive case accepted. |
| R1-10 | Amount Financed/EIR and classification requirements fail closed when their own approved source is absent; they are never aliases or residuals. |
| R1-11 | Concurrent same-request submissions return one recorded version; conflicting reuse and competing supersessions fail deterministically. Forced audit failure leaves no partial transition. |
| R1-12 | Applicable rule/source supersession racing approval/release cannot produce a stale accepted packet; unchanged committed-result readback has no new side effects. |
| R1-13 | Documents, signing evidence and cash authorization consume the same bound snapshot. Wrong packet/source, changed planned release date and cancelled approval cannot be used. |
| R1-14 | Released schema-1 originals stay byte-identical and readable; unreviewed new approvals cannot exploit the legacy decoder. Completed release replay remains singular. |
| R1-15 | Actual-event accounting remains separately permissioned and idempotent after real synthetic release/collection; no automatic General Ledger posting is introduced. |
| R1-16 | Each supported Web/Android/Windows consumer displays the authoritative breakdown, blocks unsupported inputs, handles uncertain readback and clears private context on logout/account change. |

Implement the tests before their owning product changes. Record the actual failing reason, minimal correction and passing affected evidence. Retain existing onboarding, schedule, tax-accounting and document regression coverage. Reuse valid unchanged evidence; do not rerun unrelated successful jobs merely for another Green signal. Changed heads must meet the existing required checks.

## 10. Ownership and completion gates

R1 owns proposed disclosure-source model/repository/API/storage bindings, first-loan approval/packet/document integration and corresponding tests. R2/#450 retains backend renewal-summary ownership; R6/#451 retains staff money serializers/models; R9/#452 retains temporary mobile-photo ownership. Shared schedule, tax-rule writers, schema and UI form edits require explicit coordination in #448. No migration ID or shared-file reservation is created by this specification.

Subsequent implementation planning should produce reviewable dependent slices: source/evidence binding; supported component/document integration; and downstream cash/accounting/cross-surface acceptance. Use the existing PR where appropriate rather than opening empty parallel PRs.

R1 is complete only when applicable positive tax-bearing cases, not just blocked or zero fixtures, are supported by the authoritative component model and reconcile through the full approved lifecycle. Unsupported business inputs remain blockers; a passing source-only test suite or documentation CI cannot close the audit item.

## 11. Specification review and next checkpoint

Self-review covered: no pre-release dependency on nonexistent actual events; application binding before loan ID creation; distinction between reviewed support and machine/legal proof; unsupported GRT split; company tax versus borrower charge; exact money; replay and concurrent supersession; legacy released originals versus new actions; private evidence; and other-PR ownership. No new executable regression was run for this document.

Next: Management reviews this written specification. Approval permits preparation of the implementation plan; product changes then follow that reviewed plan and tests-first execution. The approved design direction need not be asked again. Do not substitute repeated baseline-CI checks or generic source searches for this next artifact. PR #449 stays Draft; no merge, deployment, private settings, real records or financial actions are authorized here.

## 12. Source references

- [Approved-direction proposal and inspected source timing](https://github.com/GILBIC/spina-lending-app/pull/449#issuecomment-5771584897).
- [Existing approval API](https://github.com/GILBIC/spina-lending-app/blob/17591f4b87f38c6be70f24c0e64e225753108e17/gilbic_backend/src/gilbic_backend/first_loan_api.py).
- [Existing approval packet and lifecycle](https://github.com/GILBIC/spina-lending-app/blob/17591f4b87f38c6be70f24c0e64e225753108e17/gilbic_backend/src/gilbic_backend/first_loan_repository.py).
- [Existing terms, components and digest](https://github.com/GILBIC/spina-lending-app/blob/17591f4b87f38c6be70f24c0e64e225753108e17/gilbic_backend/src/gilbic_backend/first_loan_terms.py).
- [Existing document projection](https://github.com/GILBIC/spina-lending-app/blob/17591f4b87f38c6be70f24c0e64e225753108e17/gilbic_backend/src/gilbic_backend/loan_document_tax_breakdown.py).
- [Actual-event tax evidence schema and guards](https://github.com/GILBIC/spina-lending-app/blob/17591f4b87f38c6be70f24c0e64e225753108e17/gilbic_backend/sql/0082_add_v1_tax_evidence_readiness.sql).
- [Gap audit and parallel coordination](https://github.com/GILBIC/spina-lending-app/issues/448).
- [Separate actual go-live and accounting acceptance](https://github.com/GILBIC/spina-lending-app/issues/443).
