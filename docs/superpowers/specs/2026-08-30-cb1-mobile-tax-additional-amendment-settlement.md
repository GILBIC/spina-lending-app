# CB1 Mobile Additional-Tax Amendment and Settlement Slice

## Status

Approved frozen-roadmap slice. This document distinguishes the current protected backend from the Mobile behavior added by this slice. It does not authorize production data changes, SQL migration execution, merging, deployment, signing, release, or completion of human acceptance gates.

## Current behavior

- FastAPI and PostgreSQL already implement the Management-only protected upward tax-amendment lifecycle on Desktop routes: immutable amendment evidence, additional-liability preparation and posting, exact additional-payment evidence, and additional-settlement preparation and posting.
- PostgreSQL functions are the only financial write authority. They derive the additional tax, revised return amount, and required payment; revalidate original and replacement evidence, open periods, accounts, journals, permissions, and settlement history; and retain permanent audit evidence.
- Management Mobile currently exposes tax evidence, liabilities, base returns/settlements, and decrease/reversal corrections. Its tax launcher explicitly says additional-tax amendments remain later work.
- The existing additional-amendment API requires exact return, original liability, and replacement-evidence identifiers. Mobile must not ask Management to type or infer these internal coordinates.

## Intended behavior in this slice

Management Mobile gains one bounded **Additional tax** workspace that:

1. reads the protected amendment queue, summary, permissions, policy flags, and server-derived eligible amendment candidates;
2. records retained amended-return or additional-assessment evidence from one exact candidate;
3. separately prepares and posts the additional-liability draft;
4. records the exact server-required payment evidence only after liability posting;
5. separately prepares and posts the additional-settlement draft; and
6. preserves original return, liability, payment, and settlement history unchanged.

The workspace uses compact Mobile rows and explicit Management review presentations. Evidence recording, draft preparation, and posting remain distinct confirmations.

## Server-derived amendment candidate

The backend returns candidates only when the existing protected recording function can plausibly accept the relationship:

- an immutable filed return contains the exact original posted liability;
- the original liability is `posted_adjustment_review_required` because its evidence was superseded;
- a strictly newer, current, unprepared, unposted evidence row exists for the same tax type, source, loan, and client and has a strictly higher tax amount;
- every other liability in the filed return remains exact and posted;
- no competing correction or additional-amendment evidence reserves the return, original liability, or replacement evidence;
- the original liability fiscal period remains open;
- the original return is either unpaid, or its exact retained payment has an exact posted settlement; an in-flight payment/settlement state is excluded.

Candidate fields include the filed return and original/replacement evidence coordinates, tax/source/loan/client identity, original declared tax, original and replacement item tax, derived additional tax, derived revised declared tax, derived payment basis and required payment, original filing and recognition dates, evidence versions/digests, original fiscal-period boundaries, and any exact original settlement identity. These values are read-only hints; the protected PostgreSQL function revalidates them transactionally.

## Authority and safety boundaries

- Flutter remains a typed presentation and confirmation client, not the authority for roles, permissions, evidence freshness, tax amounts, payment basis, accounts, balances, journal coordinates, or posting eligibility.
- Desktop and Mobile aliases call the same FastAPI handlers and repositories. Every request uses Supabase bearer authentication and the approved installation identifier.
- Management role and six action-specific permissions remain server-derived. Mobile also intersects those permissions with the authenticated session for presentation gating.
- No SQL migration and no new financial write function are added. Candidate derivation is read-only over existing protected records.
- Automatic source posting remains disabled. Generic journal posting, manual balance editing, partial payment, and historical rewriting remain outside this workflow.
- Direct Client GCash remains a non-interactive Xendit placeholder. This slice only retains the existing approved accounting cash keys for tax-payment evidence.

## Fail-closed Mobile contracts

- Unknown enums, missing UUIDs, non-canonical dates/timestamps, malformed lowercase SHA-256 digests, non-cent money strings, inconsistent derived amounts, invalid policy flags, and impossible lifecycle states are rejected while parsing.
- Amendment evidence uses candidate-derived return, liability, replacement evidence, and recognition coordinates; Mobile cannot override accounting amounts.
- Payment evidence amount is always the exact `payment_required_amount` returned by the authoritative queue and is not an editable amount.
- Posting requests echo exact digests, amounts, account codes, posting dates, and fiscal-period identifiers returned by the server plus a fresh 64-character confirmation token.
- If a financial write has an ambiguous network result, every write action is disabled until a successful authoritative refresh.

## Out of scope

- Tax Recoverable refund or credit realization, partial or mixed payments, new tax rules, legal-rate inference, automatic posting, production migration execution, release approval, and human acceptance completion.
- Desktop redesign or any second authoritative backend.

## Acceptance evidence

- Backend contract tests prove shared Desktop/Mobile handlers, exact candidate derivation, response coordinates, Management/device/permission checks, and unchanged protected-function writes.
- Flutter tests prove strict lifecycle parsing, exact request bodies, approved-device headers, candidate-derived evidence, non-editable payment amount, separate confirmations, permission gating, and ambiguous-write refresh locking.
- Focused and full backend/Flutter suites, formatting, analyzer, compile checks, exact diff review, secret scan, and exact-head GitHub Actions must pass before code-complete status is reported.
