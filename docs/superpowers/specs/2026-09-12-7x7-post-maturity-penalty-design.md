# Priority #6 — 7x7 Post-Maturity Penalty Authority Design

**Date:** 2026-09-12  
**Status:** Approved design; implementation not started  
**Branch:** `priority6/7x7-contract-accounting-alignment`  
**PR:** #426  
**Frozen base:** `main` at `fd69d2f01c68c4193dc92aa1e45a7113190054b5`

## 1. Purpose

Complete the remaining Priority #6 product authority for a 7x7 loan after the exact signed contractual maturity has passed and an unpaid obligation remains.

This design adds a **separate post-maturity penalty layer** to the existing authoritative 7x7 financial replay. It does not create a second schedule engine, a second collection engine, or a second accounting ledger.

The design preserves all verified Priority #6 slices already on PR #426:

- signed schedule rows are the contractual/accounting authority;
- contract lock synchronizes loan-level agreed daily amount and exact signed maturity;
- one active 7x7 per Client is enforced while one active Regular may coexist;
- exact-term pricing/compliance readiness is fail-closed before contract lock;
- contractual 7x7 interest stops at the exact signed maturity while earned/unpaid interest remains collectible.

## 2. Product Authority

### 2.1 Trigger

Penalty may begin only **after the exact last immutable installment date of the active verified signed 7x7 schedule**.

The product default target of 60 days is not itself a penalty trigger. `loan_type.term_days`, operational maturity, rolling finish dates, borrower shortfall extensions, or other inferred dates must not replace signed contractual maturity.

Signed maturity is inclusive for contractual interest. The first possible penalty-bearing calendar day is the following day.

### 2.2 Rate and proration

Approved contractual product rate:

- **3% per month**;
- **simple / non-compounding**;
- **30-day fixed-month daily proration**;
- therefore the contractual nominal daily factor is **0.1% of the eligible penalty base per eligible overdue day**.

The charge actually assessed must also respect any lower applicable legal penalty-rate ceiling proven for that exact loan. Therefore:

**Effective Monthly Penalty Rate = min(3%, Applicable Legal Penalty-Rate Ceiling)**

If the terms-bound compliance authority does not prove either the applicable numeric penalty-rate ceiling or an explicit evidence-backed determination that no lower ceiling applies, automatic penalty assessment fails closed.

No penalty-on-penalty and no interest-on-penalty is permitted.

### 2.3 Penalty base

The penalty base is the **unpaid contractual scheduled amount that is eligible to be overdue after maturity**:

- remaining principal; plus
- contractual interest already earned through signed maturity and still unpaid.

The base excludes:

- future or unearned contractual interest;
- any penalty amount;
- unused Advance refund due;
- Refund Due;
- charges that are not legally part of the applicable scheduled amount due;
- amounts protected by a Management-approved No Collection adjustment until their current operational effective due date is reached.

After a payment reduces contractual interest or principal, the reduced contractual amount becomes the basis for subsequent penalty days.

### 2.4 Payment-date sequence

SPINA has calendar-date collection authority rather than authoritative intra-day timing. The deterministic rule is therefore:

1. determine the opening eligible overdue base for that calendar date;
2. accrue that date's eligible penalty using the opening base;
3. apply the same-day payment;
4. use the reduced contractual balance as the base starting the next calendar day.

This prevents same-day timing ambiguity and prevents a payment date from becoming an automatic free penalty day.

### 2.5 Rounding

Penalty math uses Decimal precision without daily centavo rounding.

SPINA must:

- keep fractional-cent calculations internally;
- aggregate the exact penalty over the assessment period;
- apply the applicable legal rate/cost-cap clamps;
- round only when a real financial boundary requires a centavo amount, using `ROUND_HALF_UP` to PHP 0.01.

Do not round each daily accrual before summing.

### 2.6 Post-maturity payment allocation

Approved allocation order after maturity:

1. **Past Due Contractual Interest**
2. **Past Due Principal**
3. **Accrued Penalty**

This deliberately reduces the penalty-bearing contractual base before cash is applied to the separate penalty balance.

If contractual principal and contractual interest reach zero while penalty remains, no new penalty accrues because the penalty base is zero.

### 2.7 Penalty-only state and closure

Exact post-maturity payoff is:

**Remaining Principal + Unpaid Contractual Interest + Accrued Capped Penalty**

If principal and contractual interest are zero while penalty remains:

- the contractual obligation is settled;
- new penalty accrual is zero;
- the loan is not yet Paid/Closed;
- the loan is exposed operationally as **Penalty Outstanding** until the assessed penalty is settled.

A renewal must not silently absorb or capitalize an outstanding penalty into a new loan. Any future waiver or write-off path is outside this design and requires separate Management-approved authority and audit design.

## 3. Management No Collection Protection

A borrower must not incur a penalty for an amount that SPINA/Management itself officially deferred.

For a valid Management-approved No Collection adjustment after contractual maturity:

- the protected amount does not become penalty-bearing until its current persisted operational effective due date is reached;
- the No Collection date itself accrues zero penalty for that protected amount;
- signed contractual maturity remains unchanged and continues to be the immutable contract-history date;
- borrower-caused missed or partial-payment extensions do not receive this protection merely because operational maturity moved.

The penalty layer consumes existing operational schedule and No Collection evidence. It does not create or mutate schedule rows.

## 4. Signed Disclosure and Compliance Authority

Automatic penalty assessment is allowed only when the exact loan's signed, terms-bound disclosure/contract proves that the borrower accepted this penalty policy.

The signed policy must unambiguously bind at least:

- 3% monthly simple/non-compounding contractual rate;
- 30-day daily proration;
- start only after exact signed contractual maturity;
- approved penalty base;
- applicable legal rate and total-cost caps;
- no penalty-on-penalty.

The exact signed schedule/contract settings plus the existing Priority #6 exact-term pricing/compliance fingerprint are the authority. Do not create a separate mutable loan-type penalty authority.

The current readiness evidence is not enough if it proves only Boolean readiness. Penalty implementation must minimally extend terms-bound compliance evidence, if necessary, so the server can prove the exact immutable values/basis needed for calculation, including:

- applicable penalty-rate ceiling or explicit evidence-backed no-lower-ceiling determination;
- applicable lifetime non-principal cost ceiling;
- policy/legal basis or evidence reference used for those values;
- the exact terms fingerprint they apply to.

The penalty layer must consume that evidence; it must not become a legal-applicability calculator.

If disclosure, exact-term fingerprint, legal applicability/rate/cost-cap authority, signed maturity, or required schedule evidence is missing or mismatched:

- no automatic penalty is posted;
- the automatic assessable amount is blocked/fail-closed;
- return **Management review required**;
- do not estimate or retroactively invent a penalty.

Legacy 7x7 loans that never signed this exact policy are not retroactively penalized by this subsystem.

## 5. Legal Cap Enforcement

The penalty engine must not hard-code a universal numeric legal ceiling.

The exact applicable rate ceiling and lifetime cost ceiling must come from terms-bound compliance authority for that exact loan.

### 5.1 Penalty-rate ceiling

The contractual product rate remains 3% per month, but the effective rate used for calculation is:

**Effective Monthly Penalty Rate = min(3%, Proven Applicable Legal Penalty-Rate Ceiling)**

If the proven legal ceiling is lower than 3%, SPINA uses the lower rate. If the applicable rate authority is unavailable or ambiguous, automatic penalty assessment fails closed.

### 5.2 Lifetime total-cost ceiling

Approved lifetime-cap model:

**Remaining Cost Headroom = Applicable Lifetime Non-Principal Cost Ceiling - Cumulative Counted Non-Principal Charges Already Assessed**

Principal repayment itself does not consume the non-principal cost ceiling.

For each new penalty assessment:

**Theoretical Penalty = Eligible Penalty Base × Effective Daily Rate × Eligible Overdue Days**

**Assessable Penalty = min(Theoretical Penalty, Remaining Cost Headroom)**

Once lifetime cost headroom is zero, new penalty accrual stops permanently for that loan. Later payment of already assessed charges does not create new lifetime headroom.

If the applicable lifetime ceiling/headroom cannot be proven, automatic penalty assessment fails closed.

## 6. Architecture

### 6.1 Chosen approach

Extend the existing protected 7x7 replay with a **separate post-maturity penalty layer**.

Authoritative flow:

**Signed Schedule → Existing 7x7 Financial Replay → Post-Maturity Penalty Layer → Existing Payment/Payoff Posting**

The existing allocator remains the sole authority for contractual interest/principal behavior. The penalty layer consumes its post-maturity contractual state and adds only the separate penalty amount/evidence.

### 6.2 Inputs

The penalty layer receives server-authoritative data only:

- active verified signed schedule and immutable maturity;
- current remaining contractual principal;
- earned/unpaid contractual interest through maturity;
- persisted operational No Collection/effective-date protection;
- signed policy/disclosure evidence;
- exact-term compliance rate/cost-cap authority;
- cumulative counted lifetime non-principal charges;
- previously assessed penalty balance and assessed-through boundary;
- authoritative collection/payment date.

### 6.3 Outputs

The shared replay/backend contract should expose authoritative fields sufficient for all consumers, such as:

- `penalty_status`;
- `projected_penalty`;
- `assessed_penalty_balance`;
- `penalty_base`;
- `effective_penalty_rate`;
- `remaining_cost_headroom`;
- `exact_payoff_total`;
- `management_review_required_reason`.

Status vocabulary should remain small and operational, for example:

- `not_applicable`;
- `projected`;
- `penalty_outstanding`;
- `cap_exhausted`;
- `management_review_required`.

Exact names may follow repository conventions during implementation, but semantics must not change.

## 7. Persistence and Audit Evidence

The existing `lending.loan_installment_payment_allocations` table is tied to immutable contractual installments and must not be overloaded with post-maturity penalty evidence.

Add the minimum append-only penalty evidence required for auditability.

### 7.1 Penalty assessment evidence

Persist one immutable assessment record only when SPINA reaches a real financial boundary such as payment, payoff, or closure.

The assessment evidence must preserve enough data to reproduce why the amount was charged, including at least:

- loan and exact signed schedule/version identity;
- assessment start/end or prior `assessed_through_date` boundary;
- opening eligible penalty base;
- eligible overdue-day count or equivalent auditable period representation;
- Management No Collection exclusions/protected amounts needed to explain the result;
- contractual penalty rate and proven applicable legal rate ceiling/effective rate;
- exact unrounded theoretical calculation;
- lifetime cost-cap/headroom authority and amount used;
- final rounded assessed centavo amount;
- policy/disclosure/fingerprint identity;
- actor/transaction context when relevant;
- creation timestamp.

No per-day penalty rows are required.

### 7.2 Penalty payment allocation evidence

Persist a separate append-only link from an existing collection transaction to the amount applied to assessed penalty.

Penalty allocation does not need to map cash to individual daily penalty rows because daily rows do not exist. The evidence must still prevent allocating more cash than the collection transaction or more than the currently assessed penalty balance.

### 7.3 No daily cron

Do not create daily accrual rows or a daily scheduled job.

Between transactions, SPINA may calculate a read-only projected penalty as of a requested authoritative date. When a payment/payoff/closure financial boundary occurs, SPINA freezes the eligible unassessed period into one assessment record inside the posting transaction.

### 7.4 Historical immutability

Prior penalty assessment evidence is immutable.

If a later void/correction changes a previously assessed post-maturity payment, penalty-bearing base, or protected date:

- do not rewrite old assessment evidence;
- do not silently back-charge the borrower;
- automatic new penalty assessment becomes `management_review_required` until an audited correction is resolved.

A retroactive penalty correction engine is outside this design.

## 8. Runtime Flow

### 8.1 Read/preview

Read-only schedule, route, payoff, and account previews:

1. run existing authoritative 7x7 contractual replay;
2. derive signed contractual maturity from the active verified immutable schedule;
3. resolve signed penalty policy plus terms-bound legal rate/cost-cap authority;
4. run the penalty projection layer only if post-maturity and all authority is ready;
5. expose server-authoritative penalty/payoff fields.

Desktop, Web, and Android must not calculate penalty independently.

### 8.2 Payment/payoff posting

Inside the same existing database transaction used for 7x7 collection/payoff posting:

1. re-read and lock the relevant authoritative loan/penalty state;
2. rerun the contractual replay;
3. determine the unassessed eligible penalty period through the collection date;
4. accrue that payment date's penalty from the opening eligible base;
5. apply Management No Collection exclusions;
6. resolve the effective rate as the lower of contractual 3% and the proven applicable legal rate ceiling;
7. apply the lifetime legal cost-cap/headroom clamp;
8. round the final assessment to PHP 0.01 using `ROUND_HALF_UP`;
9. persist one immutable penalty assessment when the rounded assessable amount is positive;
10. apply cash in order: contractual interest → principal → assessed penalty;
11. persist penalty payment allocation evidence;
12. enforce existing exact-payoff/unallocated-cash protections;
13. commit atomically.

### 8.3 No double accrual

Persisted assessment boundaries prevent the same overdue day from being assessed twice.

Two payments on one calendar date must not create duplicate daily penalty accrual. Concurrency must serialize around the authoritative loan/penalty state before calculating a new assessment boundary.

## 9. Fail-Closed Conditions

Automatic penalty assessment must stop with a clear Management-review reason when any required authority cannot be proven, including:

- no active verified signed schedule;
- immutable signed maturity unavailable/corrupt;
- exact signed penalty disclosure absent/mismatched;
- exact-term compliance fingerprint mismatch;
- legal applicability/rate ceiling unavailable or ambiguous;
- lifetime cost ceiling/headroom cannot be determined;
- historical void/correction invalidates already-assessed penalty assumptions;
- concurrent/stale state prevents a deterministic authoritative result.

Fail-closed behavior means no guessed or silently estimated charge.

## 10. Accounting Boundary

Priority #6 creates **auditable penalty evidence and read-only accounting readiness**, not automatic accounting policy.

A read-only accounting-facing projection may expose:

- total assessed penalty;
- total penalty paid;
- penalty outstanding;
- policy/rate/cap readiness status.

This design explicitly does **not**:

- post General Ledger journals automatically;
- determine tax treatment;
- modify EIR/amortized-cost calculations;
- decide penalty-income recognition timing;
- create write-off or waiver accounting;
- capitalize penalty into principal or a renewal.

Later accounting policy must consume the immutable penalty evidence rather than hide accounting decisions inside collection logic.

## 11. API and Cross-Platform Boundary

Do not add a separate public penalty-payment endpoint unless implementation evidence proves the existing collection contracts cannot represent the approved allocation.

Existing 7x7 Collection, Combined Pay, and exact-payoff posting paths should invoke one shared penalty coordinator inside their current transaction boundaries.

Priority ownership:

- **Priority #6:** server calculation authority, immutable evidence, backend response fields, accounting-readiness evidence;
- **Priority #7/#8:** presentation of already-authoritative server fields in Web/Client/mobile surfaces;
- **later accounting-policy work:** journal/tax/recognition decisions using penalty evidence.

No Priority #7/#8 UI redesign is part of this slice.

Regular loans remain unchanged.

## 12. Migration Safety

Implementation must use the next unreserved forward migration number after rechecking all active parallel PRs immediately before coding.

Rules:

- historical migrations remain immutable;
- no production backfill may create retroactive penalties;
- existing signed schedules without the exact approved penalty disclosure remain fail-closed;
- any new legal rate/cost-cap evidence fields must be terms-bound and append-only/version-safe rather than mutable global defaults;
- no live production DB/Auth/data mutation is part of implementation acceptance;
- do not copy or merge Priority #4/#5/#7/#8 code into Priority #6 to solve unrelated concerns.

## 13. TDD and Verification

Use strict test-driven development.

### 13.1 Required RED-first behavior tests

Before production implementation, tests must require at least:

- no penalty on/before signed contractual maturity;
- first possible penalty day is maturity + 1;
- contractual 3% monthly / 30-day daily proration;
- a proven legal penalty-rate ceiling lower than 3% reduces the effective rate;
- missing/ambiguous legal rate authority fails closed;
- opening-base-before-same-day-payment behavior;
- no daily centavo rounding bias;
- Management No Collection protection;
- borrower-caused extension does not itself postpone penalty authority;
- no penalty-on-penalty;
- lifetime legal headroom clamps accrual;
- zero/unknown lifetime cap authority fails closed;
- missing/mismatched signed disclosure fails closed;
- legacy/undisclosed schedules receive no automatic penalty;
- contractual principal+interest at zero stops new penalty accrual;
- penalty-only state remains collectible and prevents Paid/Closed until settled;
- allocation order is interest → principal → penalty;
- exact payoff includes projected rate- and cost-capped penalty.

### 13.2 Required PostgreSQL/integration proof

Integration tests must prove at least:

- immutable assessment evidence is append-only;
- the same period/day cannot be assessed twice;
- two same-day payments do not create duplicate daily penalty;
- concurrent postings serialize deterministically;
- penalty allocations cannot exceed transaction cash or assessed penalty balance;
- exact signed schedule/fingerprint and legal rate/cost-cap authority are enforced;
- void/correction affecting prior assumptions moves future automatic assessment to review-required instead of rewriting history;
- Regular behavior remains unchanged.

### 13.3 CI

Extend the existing GitHub-hosted dedicated 7x7 PostgreSQL workflow. Do not create a second dedicated 7x7 workflow.

Before claiming Green on any implementation head, require exact-head success for:

- full SPINA CI, including all required lanes;
- dedicated GitHub-hosted 7x7 PostgreSQL validation.

The low-friction user protocol remains valid: Management may report only `Red` or `Green`, but exact PR head and matching runs must always be verified before action.

## 14. Acceptance Boundary

A Green implementation of this design proves only that the **Priority #6 post-maturity penalty authority/evidence layer** is correct and protected.

It does not prove completion of:

- accounting journal/tax/recognition policy;
- Web/Android presentation work owned by Priority #7/#8;
- deployment/production migration;
- waiver/write-off functionality;
- retrospective correction automation;
- any legal applicability rule not supplied through the approved terms-bound compliance authority.

No Ready-for-review transition, merge, deployment, production DB/Auth/data mutation, or live penalty assessment occurs without explicit Management approval.

## 15. Approved Design Summary

The approved product and implementation direction is:

**Exact signed maturity → contractual interest stops → if an eligible contractual amount remains overdue and the exact signed disclosure plus terms-bound legal rate/cost-cap authority is ready, assess a separate contractual 3%/month simple penalty using 30-day daily proration but reduce it to any lower proven legal rate ceiling → protect Management-approved No Collection amounts/days → clamp by lifetime legal cost headroom → round only at financial boundaries → allocate payment to contractual interest, then principal, then penalty → stop new penalty when contractual base reaches zero → keep any remaining assessed penalty as Penalty Outstanding until settled.**
