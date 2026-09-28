# Office first-loan configuration and recovery

This implements the approved office-only onboarding design. It does not enable public applications, auto-approve legal forms, connect a biometric provider, or deploy a production service. The R1 source-review foundation requires migrations through 0129, using the existing reviewed migration process before enabling these routes. Current implementation and unmet acceptance gates are recorded in [the R1 execution state](../workstreams/2026-09-28-r1-execution-state.md).

## Staff workflow

1. Employee or Management records office intake and its requirement evidence. Collector records the residence visit through the protected visit workspace. Management alone may use the existing eligibility bypass.
2. An eligible applicant resolves to one inactive Client. Staff encodes and reviews its current CIF, captures the actual applicant-signed review, records the approved baseline/liveness result, and obtains Management activation. Corrections after confirmation create a new review cycle.
3. Staff records the separate first-loan application and captures applicant confirmation of its exact saved version. Optional employment and reference details remain optional. The in-office saved review can be printed.
4. Staff provides the exact configured privacy notice and consent PDFs. The applicant acknowledges those versions; optional service communications start unchecked and are not required for a loan.
5. Management obtains the disclosure context for the exact proposed terms, current CIF, confirmed application and selected effective tax-rule evidence. Management records the reviewed calculation and private support, then approves using that saved calculation ID and digest. Approval stores an immutable packet in the existing loan model, without a release date, active schedule or account credentials. The existing exact 7x7 pricing review remains required for that product.
6. Management generates the locked packet. Staff downloads it, witnesses the named borrower's wet signature and uploads the actual signed scan. Management authorizes release of that exact packet. The final handoff separately records the actual cash acknowledgment.
7. Office release commits the loan, actual Manila release date, existing authoritative schedule, disbursement/accounting evidence, receipt and unique credential intent atomically. The existing managed Client account lifecycle then runs separately. Web and mobile servicing read the stored first contractual payment date.

An approval's release-date basis must match the actual server release date. If it does not, cancel the unreleased approval, approve revised terms, regenerate documents and obtain new signatures. Staff cannot change approved terms during cash handoff.

## Private evidence

### Disclosure review and recovery

The protected first-loan prefix is `/api/v1/management/first-loans`:

- `POST /disclosure-context`: Management supplies exact source IDs, terms and rule IDs; the server returns its context digest without creating a review or financial event.
- `POST /disclosure-calculations`: Management supplies that context, exact reviewed components, independently supported disclosure values, itemized charges and a PDF/PNG/JPEG support file bounded to 10 MiB. The server retains actor/device/time and derives readiness. Uploading a balanced calculation does not make it ready for approval.
- `GET /disclosure-calculations/by-request/{request_id}`: the reviewing Management actor recovers the saved result after a lost response. Reuse the original request identity and identical content; do not submit another review just because a response was interrupted.
- `GET /disclosure-calculations/{id}?application_version_id=...`: authorized office readers see only the exact application's public financial summary and current blockers.
- `GET /disclosure-calculations/{id}/support?application_version_id=...`: Management alone downloads verified private support bytes. No public link or storage path is returned.

All routes require a persisted active device and the existing review/approve permission. Validation diagnostics omit rejected private bodies and support bytes. Missing source pairs block new approvals; old completed replay remains subject to current access controls. A changed application, CIF, rule or superseding review may require controlled cancellation and a new approval/signature cycle. Never rewrite a signed original or backfill zero taxes.

Positive upfront deductions require retained reviewed charge authority, complete disclosure values and compatible existing schedule/cash amounts. Positive scheduled GRT or other scheduled charges remain blocked with `component_integration_required` until their owning schedule/allocation path supports them. Amount Financed, finance charges and EIR are saved independently; none is inferred from cash proceeds. This workflow does not post an actual tax liability or enable automatic source posting. Web/Android form integration and full positive-component/accounting acceptance remain separate tracked work.

Set `GILBIC_OFFICE_REVIEW_EVIDENCE_ROOT` to an absolute persistent directory outside the repository and web root, writable only by the backend identity. It holds immutable PDF/PNG/JPEG evidence and generated packets, each bounded to 10 MiB and verified by SHA-256. Back up this directory together with its database metadata. Losing either side blocks signing/release instead of accepting a free-text receipt reference. Browser uploads never select filesystem paths.

Downloads use the protected API with active office/device authorization and `Cache-Control: no-store`. API traffic is excluded from the service worker. Do not place private evidence beneath a static host or CDN directory.

## Privacy package

`GILBIC_PRIVACY_PACKAGE_MANIFEST` points to an absolute JSON file controlled by the operator. It contains:

```json
{
  "approved_for_issuance": false,
  "facts": {
    "registered_lender_name": "",
    "registered_office_address": "",
    "dpo_name": "",
    "dpo_email": "",
    "retention_schedule_version": "",
    "provider_disclosures_version": ""
  },
  "notice": {"version": "", "sha256": "", "path": ""},
  "consent": {"version": "", "sha256": "", "path": ""}
}
```

Complete the approved facts and absolute PDF paths before setting approval true. Empty values and known draft placeholders keep signing unavailable. A document version may not be reused for different bytes. Each acknowledgment retains both versions, hashes, separate optional choice, source CIF, witness and protected scan.

The September 19 counsel files are preserved in [the source archive record](../forms-documents/2026-09-19/README.md). Their unresolved facts and wording checks remain open; copying the drafts is not production approval.

## Legal packet templates

`GILBIC_FIRST_LOAN_TEMPLATE_MANIFEST` points to an absolute, operator-controlled JSON file. Required keys are:

- `version` and `approved_for_execution`.
- `documents.disclosure`, `documents.agreement`, `documents.promissory_note`: each has an absolute PDF `path` and exact `sha256`.
- `annex_a.path` and `annex_a.sha256`: the retained R2 DOCX source, SHA-256 `80ef81aec3141f9c96a5d78f1edd1e7367c8a6be9ab7dca92e81b07756217ddb`.
- `disclosure_rules.regular` and `disclosure_rules.seven_by_seven`: each has the finalized `allocation`, `post_maturity` and `interest_basis` wording.
- `agreement_annex_mode`: `separate_complete_annex`, confirming the configured agreement uses the complete separate Annex rather than a competing abbreviated schedule.

The three legal PDFs use named plain-text fields from `first_loan_documents.packet_fields`. Each must include loan number, borrower name, principal, installment amount, first-payment date and maturity date. Unknown financial fields, active PDF content, incomplete sources or altered bytes block issuance. Unsupported financial values are never guessed. Template preparation must confirm all mandatory legal information is represented before approval.

For schema-2 packets, both disclosure and agreement PDFs must also contain itemized `deductions`, `dst_upfront`, `grt_in_repayments`, `other_upfront_deductions`, `other_scheduled_charges`, `total_upfront_deductions`, `net_proceeds`, `contractual_interest`, `total_scheduled_payable`, `disclosure_calculation_id` and `disclosure_review_digest`. The disclosure additionally requires `amount_financed`, `finance_charge_total`, `non_finance_charge_total`, `effective_interest_rate`, `rate_period` and `calculation_method`. Values come from the bound immutable snapshot and reconcile with the saved schedule and cash amounts. Internal support references and review rationale are excluded. An older template missing any required field blocks new generation; already issued historical bytes remain unchanged.

The bundle digest returned by `first_loan_documents.template_bundle()` includes document hashes, Annex hash and product disclosure text, but excludes machine-specific paths. Configure that exact version and digest in `lending.first_loan_document_templates` through the existing protected operational process. The application seeds no approved template. Retire a changed template and configure a new version; do not reuse its version.

`GILBIC_OFFICE_DOCUMENT_CONVERTER` points to the approved absolute LibreOffice executable. The converter runs headlessly with an isolated temporary profile and a bounded timeout. The same retained Annex layout, existing schedule projection and embedded-Arial check used by the Annex proof are reused. Install the licensed Arial faces in the converter environment; font substitution blocks issuance. Do not commit or distribute font files.

The renderer fills and flattens the three legal documents, appends every approved installment in the complete Annex, verifies the final non-fillable PDF and retains its hash. For 7x7, the exact existing reviewed pricing policy is pinned to the generated document; a later changed review cannot silently change the signed policy at release.

## Interrupted operations

After a lost response, reload the authoritative record before acting again. Stable request identities and immutable source hashes make repeat calls idempotent; changed terms cannot reuse a prior request. Existing captured evidence and release/receipt state are returned by protected readback.

Credential setup is intentionally outside the financial transaction. It reserves one Auth UUID before contacting the provider and reconciles that UUID plus its server-owned provisioning marker after interruptions. It never links by matching email alone, stores a password, deletes an Auth identity after an uncertain commit, or repeats cash release to retry credentials. Use the protected credential retry action; once linked, use the existing password-reset workflow if the one-time response was lost.

First-loan approvals cannot be activated through the older generic schedule/disbursement paths. A committed first-loan disbursement cannot be voided independently of its receipt and schedule; a reviewed reversal workflow is required.

For Clients enrolled in CIF, shared new-loan and renewal approval, cash handoff and execution also require a current active, unexpired CIF without unresolved re-verification. A flag added after approval blocks subsequent release. A routine review-due reminder alone does not block borrowing. Existing-loan collections, payment corrections, receipt acknowledgments and recorded-event retries remain available; historical Clients without CIF retain the existing path. If a concurrent CIF edit returns a conflict, refresh the saved state before retrying the intended action.

## Verification

The combined local database runner is `tools/run_client_onboarding_disposable_postgres_validation.py`. It requires `SPINA_ALLOW_DISPOSABLE_DATABASE=1`, accepts a loopback disposable PostgreSQL connection only, creates a fresh `spina_onboarding_*` database and drops it in `finally`. It replays schema through 0129, then runs existing eligibility/CIF/application proofs together with evidence, privacy, approval, release, credential, shared new-credit CIF guard and disclosure source/recovery proofs. External Auth and mail are synthetic test doubles.

Run the backend suite, `npm test`, relevant Flutter tests, the combined disposable database proof and the real converter/Arial/PDF proof before marking the workflow accepted. R1 delivery is tracked in PR449 and issue448; PR420's original implementation history is not the current release gate. Deployment and production activation require the actual configuration and acceptance evidence.
