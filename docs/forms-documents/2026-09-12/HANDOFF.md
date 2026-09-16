# Template register, field mapping and PDF acceptance checklist

Text-only review mirror of the complete seven-page source handoff. Page references refer to the original DOCX. The original source package remains unchanged; this is not implemented application behavior.

Source: `Handoff/SPINA_Template_Register_Field_Mapping_PDF_Checklist_2026-09-12.docx`

Source DOCX SHA-256: `15fe57133008396a4112e085614d16d69cbca3b4089babe0efbb51e58e685d60`

```text
CURRENT TEMPLATE REGISTER

Field mapping and PDF-generation validation checklist

SOURCE-BASED WORKING HANDOFF • 12 SEPTEMBER 2026

This package consolidates the ten current working templates below. It preserves their wording and file bytes; it does not approve production use, issue a borrower document, or implement autofill, signing or financial calculations.

1. Current working versions

ID | Document | Revision | Pages | Use
T01 | Loan Application Form | R2 | 4 | Application / CIF review
T02 | Cash Loan Agreement | R3 | 7 | Contractual packet
T03 | Loan Disclosure Statement | R2 | 4 | Contractual packet
T04 | Promissory Note | Clean draft | 4 | Contractual packet
T05 | Schedule of Payments / Annex A | R2 | 2 | Complete schedule layout
T06 | First-Loan Office Release / Cash Receipt | Clean draft | 2 | Actual office cash handoff
T07 | Notice of Delinquency / Default | Clean draft | 2 | Account notice
T08 | Demand Letter | Clean draft | 2 | Account demand
T09 | Data Privacy Consent and Authorization | Approved reformatted | 3 | Separate consent evidence
T10 | Privacy Notice | R2 | 4 | Separate privacy information

* Page counts are the existing reviewed working layouts, not final loan-packet counts. T02 and T04 include conditional notarial components. T05 has two example layout pages, not a complete borrower schedule or a page limit.

Exact files, not similarly named older copies

The Templates folder contains one current file for each ID. README.txt gives the full filename for each ID; manifest.json records the exact filename, source file ID, byte count and SHA-256. R2/R3 identify editing revisions, not an issued borrower document version.

Package scope

This is the current legal-template set, not a declaration that every operational document is finished. Renewal field-release evidence, payment receipts, Statements of Account and the separate internal System Alignment Change Memo are outside this ten-template bundle; their completion is not established by this register.

Source basis: T01–T10; prior consistency review; GitHub checkpoints G1–G4 identified on Page 7. No older contract is superseded by assembling this package.

2. Field mapping — identity, application and privacy

The following is a source-family map derived from the templates. It identifies what must supply each field and what a person may enter. It is not a verified database/API binding. Except for the code members identified on Page 3, exact keys and end-to-end bindings remain OPEN.

ID | Fields / displayed values | Required authority and edit boundary
M01 | Lender name, registered office, official contact details | Controlled company settings. Read-only in generated documents; do not substitute a placeholder brand for the final registered identity. Actual values/configuration keys remain open. [T01–T10]
M02 | Borrower name, address, birth/civil/citizenship/contact details; Client/CIF reference | Applicable verified CIF record and document snapshot. Historical signed documents retain their locked CIF version; a later profile update must not rewrite them. [T01 I; T02 §17; T04 opening]
M03 | Requested type, amount, purpose, arrangement, term, first-payment preference and repayment source | Application-stage values, entered or confirmed in SPINA under the existing workflow. Keep requested terms distinct from Management-approved contractual terms. [T01 II]
M04 | Employment/business, income, existing obligations, references and emergency contact | Applicant declarations/CIF values. Reuse known data; accept only required input/corrections through its source workflow. Do not turn a declaration into verified evidence by autofilling it. [T01 III–V]
M05 | ID evidence, address proof, residence visit, income proof, identity/liveness and processing status | Existing pre-CIF/CIF workflows. Read-only statuses and evidence references; a pre-CIF exception is not a liveness bypass or proof of activation. [T01 VI, X]
M06 | Application/account numbers, Document ID, template/packet/schedule versions and generation time | System identity/version records and actual generation event. Preserve distinct identifiers and timestamps. A future loan/packet ID must not be invented during application intake. [T01 control; T02/T05 footers]
M07 | Privacy Notice version/effective date, DPO contacts, retention and provider details | Versioned privacy/company records confirmed for real operations. DPO contact, retention and provider/cloud disclosures are unresolved professional-review inputs, not defaults to invent. [T10 §§1,9,13–15]
M08 | Consent version, Notice version acknowledged, optional choice, signature/evidence, actor and acknowledgment time | Actual privacy acknowledgment and consent evidence. Optional choice starts unchecked and remains separate; refusal is not automatically refusal of necessary processing. CIF supplies identity status. [T09 IX–XII]

Repeated generic tokens such as {Amount}, {Date} or {Applicant/CIF value} must be identified by document, section and row context. A shared spelling does not prove that two fields have the same business meaning.

3. Field mapping — approved terms and schedule

ID | Fields / displayed values | Required authority and validation
M09 | Gross Principal, deductions, Amount Financed, authorized Net Proceeds | One locked Management-approved disclosure calculation. Distinguish every amount; reconcile deductions and prepaid/scheduled charges without counting a charge twice. Exact legal/accounting mapping remains open. [T02 §3; T03 III,V–VI]
M10 | Interest rate/period/method, fixed daily interest, total interest, finance charges, percentage and EIR | Approved loan-specific pricing/disclosure calculation and exact schedule. No universal 42% insertion; no unverified annualization. Required pricing and accounting checks precede contract lock. [T03 IV]
M11 | Frequency, agreed installment, count, first date, term and Contractual Maturity | Same locked approved schedule/terms across T02–T05. Last contractual installment date is maturity; operational finish is a separate servicing value. [T02 §2; T03 II,VII; T05 I,III]
M12 | Installment number/date, Principal, Interest and Total Due | Authoritative contractual rows, in order, without recalculation of the loan in the PDF layer. The 7x7 code members listed below are verified at a pinned read; the output binding remains open. [T05 II; C1]
M13 | Scheduled Remaining Principal, including the final summary | Original contractual principal less cumulative scheduled principal components through the row in the same locked version. Excludes interest/fees/penalties; not live balance or payoff. This is the approved definition’s projection, not a second schedule engine. [T02 Annex; T05 II; G1]
M14 | Other scheduled charges; late/default/penalty and prepayment displays | Exact selected, disclosed rule and validated amounts. None/zero when genuinely inapplicable; missing readiness is not a silent zero or permission to charge. Penalty base/proration/cap readiness remains open. [T03 V,VIII–IX; T05 III]
M15 | Payment allocation and permitted payment paths | Exact approved product rule from the locked Disclosure. No staff selection of allocation order; preserve Advance, Extra Principal/Principal Reduction and Refund Due distinctions. [T02 §7; T03 VII]
M16 | Principal/interest/charge totals and original scheduled payable | Reconcile the complete approved row set to the same Disclosure. Final principal reconciles without manual adjustment. Do not include hypothetical future penalties in the on-time schedule. [T03 V–VII; T05 II–III]

C1. Verified 7x7 source members — not an implemented PDF contract

SevenBySevenSignedInstallment exposes installment_number, due_date, contractual_amount, principal_component and interest_component. It does not expose a stored Scheduled Remaining Principal or other-charge member. Read at PR #426 metadata head 8bc4df317966bbc435a0467c6a3050f15743282a. This read does not verify Regular mapping, database joins, a deployed endpoint or pricing legality.

4. Field mapping — execution, release and notices

ID | Fields / evidence | Required authority and event boundary
M17 | Management approver/authorizer, role, authority, approval reference and time | Authenticated approval record for the exact packet. No free-typed substitute name or unaudited signature image. Approval is separate from borrower execution and actual handoff. [T02 execution; T04 execution; T06 I]
M18 | Borrower signature, printed name, signed date and evidence link | Real wet signature or the separately approved electronic-signature evidence. Signed time is not assumed from upload time. A signing-ready PDF may have deliberate signature lines; a signed evidence copy must have the required completed evidence. [T04 §8; T05 IV; G3]
M19 | Actual cash handed, handoff time, releasing staff/witness, receipt reference and borrower cash acknowledgment | Actual authenticated office handoff event. Cash must exactly match authorized Net Proceeds. Do not prefill actual receipt as completed from Management approval or PDF creation. Failed handoff preserves the signed packet without activation/credentials/partial release. [T06 I–III]
M20 | Notice state/title/body, account values, due dates, amount due and demand total | One authoritative posted-account/schedule snapshot as of its computation time, plus the approved legal/contractual state. Do not replace currently due amounts with an entire balance unless supported. Exact state/amount binding still requires review. [T07 I; T08 I]
M21 | Issued deadline, issuer/contact/channel, issuance/send time and provider delivery status | Authorized notice event and linked transmission audit. Deadline/contents lock at issuance. Generated is not Sent/Delivered; subsequent payments or transmission events do not overwrite the issued PDF. [T07 II, audit; T08 II, audit]
M22 | Notarization selection, appearance/ID particulars, notary records and final document page count | Approved internal policy/exception and notary/counsel-controlled completion. Omit the component when not required. Count the actual assembled instrument, not the ten-file bundle. Management approval is not a notarial act. [T02 notarial component; T04 Page 4]
M23 | Signed copy, integrity hash, document-to-loan link and read-only access | Retained exact document/evidence version and its integrity reference. Corrections create a new version; no silent replacement of the historical signed copy. Authorization and storage bindings remain to be tested. [T04 final controls; G3]

Human input is limited to the real workflow step

SPINA remains the fill-and-validation interface. Staff may encode permitted application facts and workflow confirmations; borrower signatures, optional choices and actual receipt confirmations must reflect real acts. Calculated terms, verification results, approved identities and server timestamps are not free-text overrides. [T01; T06; T09]

5. Assembly checklist — what is generated together

This is a testable assembly specification drawn from the current templates. The files are not merged or issued by this handoff. [T02 §23; T05 III–IV; T06]

Stage | Documents and release condition
Application / privacy | T01 is the application/CIF-review record. T09 and T10 remain separate consent/information documents, linked by the exact versions. This stage is not final contractual acceptance or cash receipt.
Contract review and signing | T02 + T03 + T04 + complete T05, using the same approved loan/packet and locked schedule. T05 replaces/expands the abbreviated Annex region at assembly; do not attach two competing schedules.
Actual office release | T06 only after the applicable approvals, complete signed packet and real successful handoff. Its actual receipt fields are not marked completed by generating the contractual packet.
Servicing notice / demand | T07 or T08 is generated for the authorized event and snapshot. It is not part of initial signing merely because its template is in this ZIP. Sending/delivery is recorded separately.

Before a signing-ready PDF

01. Select the correct template, product, borrower/CIF snapshot, approval and schedule version. Block missing or mismatched business values; do not fill them with guesses.

02. Resolve the selected fee/penalty branch and remove internal generation/review instructions from an issued copy. A genuine no-charge branch is explicit; an unresolved charge gate blocks use.

03. Emit every installment exactly once. For N ≤ 7 omit unused rows/continuation; otherwise emit rows 8 through N−1, then final N once. Place totals and acknowledgment after the real final row.

04. Keep the optional notarial component separate until its applicability is established; recalculate page totals after conditional sections and actual schedule pages are assembled.

05. Validate the exact approved financial values across the Agreement, Disclosure, Note and full schedule. Printing must not create an approval, signature, loan release, payment or notice-delivery event.

After real signing and at actual release

For wet signing: generate the signing-ready PDF, print, obtain real signatures, then retain the signed scan against the same exact version. Do not require a fabricated signature before printing. Actual cash acknowledgment is completed at handoff; a failed handoff leaves the signed unreleased packet preserved. [T04 §8; T06; G3]

Deliberate wet-signature/notarial completion lines are stage-specific, not unresolved financial fields. This does not authorize issuing a draft with missing approved terms or claiming an unsigned file is signed.

6. PDF-generation acceptance — tests still to run

All application-level tests below are NOT RUN in this consolidation. These cases translate the existing boundaries into proposed verification evidence; passing file/hash checks does not establish application acceptance.

Test | Scenario | Expected evidence — NOT RUN
A01 | Correct template and source versions | Latest registered template is selected; cross-borrower, stale CIF/approval or mixed packet/schedule references cannot produce a valid final packet. [T02; T05]
A02 | Missing and contextual fields | Unresolved required values and internal notes block final issuance. Generic Amount/Date tokens map by section/row; legitimate pre-signature lines remain possible. [T01; T03; T04]
A03 | Financial reconciliation | Approved principal/deductions/financed amount/net proceeds/rates and totals match across T02–T06. Repeated charge descriptions are not second charges. [T03 III–VII]
A04 | Complete schedule boundaries | Use synthetic N=1,7,8,60,104 cases: no missing/duplicate row; repeat identity/headers; final row, count, due date and totals match the source. [T05; G2]
A05 | Scheduled Remaining Principal | Verify same-version original principal less cumulative scheduled principal; exclude interest/fees/penalties; final principal reconciles. Later payment activity does not rewrite the signed projection. [T05; G1]
A06 | 7x7 maturity and charge eligibility | Signed maturity, not default Day 60, controls the interest boundary. Unready penalty branch is blocked; historical None/zero terms are not changed. No pricing-law test is certified here. [T02 §4; T03 VIII]
A07 | Signing and conditional notarization | Unsigned printing does not assert signing; signed upload preserves real evidence. With/without notarial components produces correct final counts; upload time is not signed time. [T04; G3]
A08 | Release success and failure | Approval/preview creates no receipt. Exact successful handoff is separately evidenced; cancellation/mismatch/incomplete handoff leaves Approved/Pending Release and no activation/credential/partial state. [T06]
A09 | Privacy choice and audit | Optional consent starts unchecked, is not a loan prerequisite and is recorded separately; exact Notice/Consent versions and real evidence remain linked. [T09 IX–XII]
A10 | Notice issuance versus delivery | Correct state/title and snapshot, locked deadline, no invented acceleration; Generated is not Sent/Delivered. Later payments/delivery updates preserve the prior issued copy. [T07–T08]
A11 | Layout and non-fillable output | Folio 8×13, black text/neutral tables/original pink logo only; long names/addresses and multi-page schedules remain readable. No clipped rows, omitted pages or incorrect Page X of Y. [G4]
A12 | Retention, integrity and authorized retrieval | Normal non-fillable PDF and real signed evidence are linked to their versions and integrity references. Test permitted read-only retrieval and denial to a different borrower; correction retains the old copy. [T04 controls; G3]

For each test, record result, exact fixture/source versions, implementation commit, artifact hash and reviewer/date. No entry above is marked Passed. Proposed synthetic case sizes test layout/completeness; they are not approved live-loan pricing examples.

7. Open gates, evidence and next implementation step

Remaining gates are explicit — not new borrower requirements

Gate | Evidence needed
Professional financial review | Amount Financed/net-proceeds reconciliation, charge classifications, required rate/EIR treatment and applicable pricing limits. The packet does not supply legal clearance. [T03]
Penalty details and implementation | Exact disclosed overdue base, partial-month convention, applicability, legal/total-cost caps and server enforcement. The conditional 3% direction is not a completed deployable charge rule. [T02 §4; T03 VIII]
Company and privacy operations | Final registered identity/contacts, DPO details, actual retention schedule and providers/cloud or cross-border facts. Do not invent them to eliminate placeholders. [T10]
Document integration and execution | Exact field/API/DB bindings, full schedule assembly, role permissions, signature/storage/audit links, retention and retrieval. Consent footer metadata also needs the common generation controls; the accepted source was not silently edited. [T04 controls; T09 XII; G3]

Evidence used for this handoff

T01–T10: exact packaged source documents and section references shown throughout this checklist. Their complete SHA-256 identities and source file IDs are in manifest.json. The source files were read and preserved byte-for-byte; previous working-layout page counts are recorded, not a claim that a real borrower packet was generated.

G1 — Approved Scheduled Remaining Principal definition (comment 5644866766) and application to both Annex locations (comment 5645020501).

G2 — Annex A completeness approval, comment 5629879504: every contractual installment and required continuation page.

G3 — Approved final PDF architecture, comment 5634734850: in-app input, non-fillable output, versioned signed evidence and wet-sign sequence.

G4 — Working R2 consistency corrections and presentation checkpoint, comment 5644204375, plus the current Notion project-state checkpoint.

C1 — gilbic_backend/src/gilbic_backend/seven_by_seven_signed_schedule.py; pinned read at PR #426 head 8bc4df317966bbc435a0467c6a3050f15743282a; blob 31a4f4111e06aaea0972681b1adff25eb2d1af3e. Only the row members described on Page 3 were checked. No CI or deployment result is inferred from this read.

Source URLs and exact document filenames are included in README.txt. The earlier consistency report is historical context; its resolved Balance-definition issue must not be reopened as unresolved.

Next bounded implementation step

Use the current Annex A R2 as the first synthetic generation target. Bind it to the existing authoritative signed schedule, then prove A02, A04, A05 and A11 before broadening to the full contractual packet. Reuse the existing schedule path; do not build a second loan, allocation or accounting engine.

This consolidation does not start that implementation, authorize a merge/deployment, or waive professional review. All ten templates remain working drafts. No live borrower data, signature, cash release, payment or notice delivery was created.
```
