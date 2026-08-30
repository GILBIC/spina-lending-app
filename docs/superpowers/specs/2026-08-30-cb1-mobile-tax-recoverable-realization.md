# CB1 Mobile Tax Recoverable Realization Slice

## Status

Approved frozen-roadmap slice. This document distinguishes the protected behavior already implemented in FastAPI/PostgreSQL from the Management Mobile behavior added here. It does not authorize production data changes, SQL migration execution, merging, deployment, signing, release, or completion of human acceptance gates.

## Current behavior

- FastAPI and PostgreSQL already implement two Management-only Desktop workflows for an exact posted `1130 Tax Recoverable`: cash-refund realization and tax-credit application.
- Refund evidence derives the full amount from one protected `recognize_settled_tax_recoverable` posting and permits only approved `1010` office cash or `1030` bank/GCash as the debit account. Its protected journal is Dr approved cash/bank / Cr `1130`.
- Credit evidence derives the same full recoverable amount, requires one unpaid retained return of the same tax type whose exact posted liabilities equal that amount, and posts Dr `2100 Tax Payables` / Cr `1130`.
- The two paths are mutually exclusive. Partial realization, mixed cash-plus-credit realization, automatic posting, generic journal edits, and historical rewrites are disabled.
- Management Mobile currently identifies refund/credit as later work and has no safe server-derived selector for the internal adjustment-posting and target-return identifiers.

## Intended behavior in this slice

Management Mobile gains one compact **Tax Recoverable** workspace with two clearly separated sections:

1. **Cash refund** lists eligible posted recoverables and the retained refund queue, records exact refund evidence, prepares the protected draft, and separately posts it.
2. **Tax credit** lists eligible recoverable/return pairs and the retained credit queue, records exact application evidence, prepares the protected draft, and separately posts it.

The workspace never asks Management to type a recoverable amount, tax-payable amount, adjustment posting identifier, or accounting entry. It presents server-derived candidates and authoritative queue values, while every financial write continues through the existing protected PostgreSQL functions.

## Server-derived cash-refund candidate

A refund candidate is returned only when:

- the adjustment is an exact posted `recognize_settled_tax_recoverable` item in the current protected adjustment queue;
- its journal remains posted and its debit is active posting account `1130 Tax Recoverable`;
- the confirmed posting amount is positive and matches the retained adjustment evidence;
- no immutable refund evidence and no immutable credit evidence already reserves that adjustment posting.

Candidate fields include the adjustment posting/evidence identifiers, tax/source/loan/client identity, exact recoverable amount, minimum realization date, retained evidence digest, entry number, and fiscal-period identifier. They are read-only hints; the protected recording function revalidates everything transactionally.

## Server-derived tax-credit candidate

A credit candidate is an exact relationship between one eligible recoverable and one target return. It is returned only when:

- the recoverable satisfies every refund-candidate source condition and is not reserved by either realization path;
- the retained return has the same tax type and its declared due exactly equals the recoverable amount;
- all return liability items are exact current posted V1 liabilities and their total equals the retained declared due;
- no cash-payment evidence, cash-settlement preparation/posting, additional-tax amendment evidence, or existing recoverable-credit evidence reserves the target return;
- the target return filing date and recoverable posting date establish the earliest valid application date.

Candidate fields add the target return identifier, period, filing date, declared due, retained return reference/digest, and the minimum application date. The protected recording function remains the final transactional authority.

## Authority and safety boundaries

- Desktop and Mobile aliases call the same FastAPI handlers and repositories. Every request uses Supabase bearer authentication and the approved installation identifier.
- Management role and the six action-specific permissions remain server-derived. Flutter intersects these with its authenticated session only for presentation gating.
- No SQL migration and no new financial write function are added. Candidate derivation is read-only over existing protected records.
- Evidence recording, draft preparation, and journal posting remain separate actions with separate confirmations. Posting echoes exact authoritative digests, amounts, accounts, dates, and fiscal-period identifiers.
- Automatic source posting, partial realization, mixed realization, manual balances, and generic journal posting remain disabled.
- Direct Client GCash remains a non-interactive Xendit placeholder. Account `1030` here is only the existing accounting cash/bank choice for retained refund evidence; it is not a client payment integration.

## Fail-closed Mobile contracts

- Unknown states, missing UUIDs, malformed dates/timestamps, malformed lowercase SHA-256 digests, non-cent money strings, invalid account codes, false policy flags, and impossible lifecycle combinations are rejected while parsing.
- The cash-refund form derives the adjustment posting and amount from one server candidate. The tax-credit form derives both the adjustment posting and target return from one server candidate.
- Preparation is available only for authoritative `*_evidence_ready` items. Posting is available only for authoritative `*_prepared` items with complete journal coordinates.
- Each write requires an explicit review presentation. If a write has an ambiguous network result, all six write actions remain locked until a successful authoritative refresh.
- Queue reads and candidate reads remain useful even when the current actor lacks mutation permission; actions are hidden or disabled by the intersection of session and server permissions.

## Out of scope

- Partial or mixed recoverable realization, new tax/legal inference, new accounting functions or migrations, production migration execution, release approval, and human acceptance completion.
- Desktop redesign, Client-side realization, direct Xendit/GCash execution, or any second authoritative backend.

## Acceptance evidence

- Backend contract tests prove shared Desktop/Mobile handlers, exact read-only candidate derivation, Management/device/permission controls, and unchanged protected-function writes.
- Flutter tests prove strict parsing, exact Mobile paths and request bodies, approved-device headers, candidate-derived coordinates, six permission gates, separate confirmations, and ambiguous-write refresh locking.
- Focused and full backend/Flutter suites, formatting, strict analyzer, compile checks, exact diff review, secret scan, and exact-head GitHub Actions must pass before code-complete status is reported.
