# CB1 Mobile Tax Settlement and Adjustment Slice

## Status

Approved frozen-roadmap slice. This document distinguishes the current protected backend from the Mobile capability added by this slice. It does not authorize production data changes, database migrations, merging, deployment, signing, or release.

## Current behavior

- FastAPI already exposes Management-only protected tax return, payment-evidence, settlement preparation/posting, and tax adjustment preparation/posting workflows on Desktop routes.
- PostgreSQL functions remain the financial authority. They enforce approved-device context, action permissions, exact immutable evidence, fiscal-period gates, balanced protected journals, idempotency, and permanent audit logs.
- Mobile currently exposes tax evidence and tax-liability review/posting only. It has no settlement or adjustment pages.
- Existing settlement and adjustment APIs require internal posting/evidence identifiers. Those coordinates are valid backend inputs but are not safe Mobile data-entry fields.

## Intended behavior in this slice

Management Mobile gains two bounded workspaces:

1. **Tax returns and settlements**
   - Read the effective settlement queue and summary.
   - Read server-derived return-liability candidates consisting only of exact, current, posted tax liabilities not already assigned to a return.
   - Let Management deliberately select candidates of one tax type and one return period. The app derives the declared total from those immutable server values; it never accepts a manually invented total.
   - Record retained return evidence and exact full-payment evidence.
   - Prepare a protected settlement draft, then separately confirm and post it using exact server-returned journal coordinates.

2. **Tax corrections**
   - Read the protected adjustment queue and summary.
   - Read server-derived correction candidates pairing an exact stale posted liability with its exact newer current unposted evidence.
   - The server derives the only currently supported adjustment kind: unpaid-liability reversal when no payment evidence exists, or settled-tax recoverable recognition when the exact settlement is posted and the replacement tax is lower.
   - Record retained adjustment evidence, prepare a protected draft, then separately confirm and post it using exact server-returned coordinates.

## Authority and safety boundaries

- Flutter is a typed presentation and confirmation client, never the authority for roles, permissions, evidence freshness, liability composition, balances, journal coordinates, or posting eligibility.
- Both Desktop and Mobile route aliases call the same FastAPI handlers and repositories.
- Every request uses Supabase bearer authentication and the approved installation identifier.
- Management role and action-specific permission checks remain server-derived. Mobile also hides unavailable actions using both server-returned and session permissions, but that is presentation only.
- Reads may expose candidate coordinates through repository queries over existing protected views/tables. No SQL migration or new financial write path is added.
- Protected PostgreSQL functions remain the only write paths and revalidate every candidate at transaction time. A stale Mobile screen must fail closed.
- Preparation and posting stay separate. Existing Management review confirmations remain mandatory; the user’s broad implementation approval does not count as a financial posting confirmation.
- Automatic source posting remains disabled. Posted history is immutable; corrections use protected adjustment evidence and journals.
- Direct Client GCash remains a non-interactive Xendit placeholder and is not changed by this slice. Tax payment evidence may continue to identify the existing approved cash account system keys only.

## Server-derived candidate contracts

### Return-liability candidate

The repository returns only base `accounting.v1_tax_liability_queue` rows where:

- `accounting_status = 'posted'`;
- posting and journal coordinates are present and the journal is posted;
- no `accounting.v1_tax_return_liability_items` row already references the posting.

Fields include tax type, posting/evidence/source/loan/client identifiers, evidence version and digest, recognition date, tax due, liability entry number, and fiscal-period identifier.

### Adjustment candidate

The repository returns only pairs where:

- the original base queue row is `posted_adjustment_review_required` with an exact posted journal;
- the replacement is newer, current `evidence_ready` evidence for the same tax type, source, loan, and client;
- the replacement is unprepared and unposted and has `evidence_ready` or `no_liability_required` accounting status;
- the original fiscal period is still open;
- no protected adjustment evidence already exists for the original posting;
- either no payment evidence exists (server kind `reverse_unsettled_liability`) or an exact posted settlement exists and replacement tax is lower (server kind `recognize_settled_tax_recoverable`).

Fields include the original posting/evidence coordinates, replacement evidence coordinates, original/replacement tax, derived adjustment amount and kind, source/loan/client identifiers, original fiscal-period boundaries, and optional settlement coordinates.

## Fail-closed Mobile contracts

- Unknown enum values, missing UUIDs, non-canonical dates/timestamps, malformed 64-character lowercase hex digests, non-cent money strings, inconsistent policy flags, and impossible action states are rejected while parsing.
- Return selection must contain at least one candidate, one tax type, dates covering every selected recognition date, a filing date on/after period end, and an exact server-derived total.
- Adjustment evidence uses the candidate-derived kind and identifiers; Mobile cannot override them.
- Posting requests echo exact digests, money, account codes, posting date, and fiscal-period identifier returned by the server, plus a one-time 64-character confirmation token.
- Ambiguous network results are reported as uncertain and force an authoritative refresh before retry.

## Out of scope

- New tax rules or legal tax-rate inference.
- Automatic source, liability, settlement, or correction posting.
- Partial tax payments.
- Additional-tax amendments, additional settlements, Tax Recoverable refunds, or credit application; these remain separate later protected workflows.
- Production SQL execution, legacy portal reconnection, Desktop duplication, release approval, or human acceptance completion.

## Acceptance evidence

- Backend contract tests prove shared Mobile aliases, server-derived candidate queries, unchanged protected-function writes, Management/device/permission checks, and fail-closed response fields.
- Flutter model/repository tests prove exact parsing and request coordinates.
- Widget tests prove discoverability, permission gating, selected-liability totals, separate evidence/prepare/post actions, and Management review confirmations.
- Focused tests, formatter/analyzer, full Flutter regression, full backend regression, compile checks, staged/post-commit diff checks, and exact-head GitHub Actions must pass before the slice is reported as code-complete.
