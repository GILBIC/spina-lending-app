# SPINA Forms & Documents — working-template handoff

Status: **documentation only; working drafts; not production-cleared**.

This directory turns the 12 September 2026 conversation package into reviewable repository documentation. It does not implement autofill, financial calculations, signature capture, PDF generation, storage, release, or notice delivery.

## What is in this PR

- Ten text-only template mirrors under `templates/`, preserving source paragraph/table order and wording.
- `HANDOFF.md`: the complete source handoff, including 23 field-mapping groups and 12 proposed acceptance cases, all **NOT RUN**.
- `manifest.json` and `README.txt`: unchanged copies of the original package's source register and guide. Their DOCX paths refer to the source ZIP, not files committed in this directory.

The formatted DOCX binaries and ZIP are **not committed in this PR**. Text mirrors are for review, search and implementation continuity; they do not reproduce the original logo, typography, page layout or dynamic Word fields and must not replace the print-layout originals.

## Exact source package

`SPINA_Current_Working_Templates_2026-09-12.zip`

- Bytes: `795483`
- SHA-256: `2dabd9db073f42c8267ecc8af07a0dd07d4e69ad719df4245c63176f2643b69e`
- Source checkpoint: [PR #420, comment 5645307722](https://github.com/GILBIC/spina-lending-app/pull/420#issuecomment-5645307722).

The ZIP remains the conversation deliverable. No sandbox link is treated as a persistent GitHub download. The manifest identifies the exact original files, including the unchanged approved Consent Form.

## Current template register

| ID | Template | Working version | Review text |
|---|---|---|---|
| T01 | Loan Application Form | R2 | [Read](templates/T01-loan-application-r2.md) |
| T02 | Cash Loan Agreement | R3 | [Read](templates/T02-cash-loan-agreement-r3.md) |
| T03 | Loan Disclosure Statement | R2 | [Read](templates/T03-loan-disclosure-r2.md) |
| T04 | Promissory Note | Clean draft | [Read](templates/T04-promissory-note.md) |
| T05 | Schedule of Payments / Annex A | R2 | [Read](templates/T05-schedule-annex-a-r2.md) |
| T06 | First-Loan Office Release / Cash Receipt | Clean draft | [Read](templates/T06-first-loan-office-release.md) |
| T07 | Notice of Delinquency / Default | Clean draft | [Read](templates/T07-notice-delinquency-default.md) |
| T08 | Demand Letter | Clean draft | [Read](templates/T08-demand-letter.md) |
| T09 | Data Privacy Consent and Authorization | Approved reformatted | [Read](templates/T09-privacy-consent.md) |
| T10 | Privacy Notice | R2 | [Read](templates/T10-privacy-notice-r2.md) |

R2/R3 identify working editing revisions, not issued borrower versions. Original DOCX files and previous versions remain unchanged.

## Preserved boundaries

SPINA is the data-entry and validation interface. The planned final output is a normal non-fillable, versioned PDF, with Document ID, versions, generated server time, page totals and a retained integrity reference. Non-fillable does not mean technically impossible to alter; integrity and historical preservation depend on the controlled storage/version/evidence path.

The contractual packet is Agreement + Disclosure + Promissory Note + **one complete Annex A**. Expand or replace the abbreviated Agreement Annex at assembly; do not issue two competing schedules. Include every approved installment exactly once. Application/CIF confirmation, privacy acknowledgment, contract signing, actual office cash receipt and notice transmission are separate events.

Scheduled Remaining Principal means the principal expected to remain after that contractual installment assuming full, on-time scheduled payments. It excludes interest, fees and penalties and is not the live account balance or payoff amount. Use the same locked scheduled principal components; do not build a second schedule or accounting engine.

The exact signed schedule determines 7x7 contractual maturity; Day 60 is not automatically maturity. The recorded 3% monthly post-maturity direction remains conditional on exact signed disclosure, applicability, overdue base, partial-month convention, caps and server enforcement. This import does not approve pricing, enable penalties or amend historical None/zero contracts.

## Next bounded implementation target

Use the existing Annex A R2 layout and authoritative signed schedule with synthetic data. Prove A02 (missing/contextual fields), A04 (all rows), A05 (Scheduled Remaining Principal) and A11 (layout) before broadening to the contractual packet. The source handoff identifies every case; none is marked Passed by this import.

Dependency ownership remains unchanged: #420 owns office onboarding/CIF/first-loan integration, #426 owns 7x7 contract/accounting authority, and the other active priorities own their respective surfaces. This documentation branch does not copy their implementation commits or create a new roadmap priority. Frozen Master #296 remains unchanged.

## Remaining gates

Professional financial/pricing review, final company/privacy details, original-format asset import, exact field/API/database bindings, complete schedule rendering, signing/storage/audit, access control and end-to-end acceptance remain open. Renewal field evidence, payment receipts, Statements of Account and the separate System Alignment Change Memo are outside this ten-template set.

Do not infer a deployment, legal clearance, production freeze, live transaction or completed PDF engine from this PR. Keep the PR Draft until its scope and remaining gates are reviewed; merge and deployment require separate authorization.
