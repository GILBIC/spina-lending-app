# 7x7 / EMER EIR and carrying-policy readiness

Status: **read-only accounting policy gate for Master Issue #296**. This document does not conclude IFRS 9 classification, approve an authoritative EIR, create an amortised-cost carrying amount, or enable accounting posting.

## Why this gate exists

SPINA's operational 7x7 rule is deliberately separate from Financial Accounting measurement:

- contractual daily interest is PHP 7 per PHP 1,000 (or fraction rounded up by the configured product rule) of **original principal**;
- partial principal repayment does not reduce that contractual daily-interest amount;
- the contract permits principal prepayment and contractual daily interest stops when principal reaches zero;
- payments settle accrued contractual interest first and then reduce operational principal.

Migration 0060 validates the exact immutable verified `signed_contract` base schedule. It proves the contractual cash-flow facts; it does not turn those facts into an IFRS 9 classification or EIR conclusion.

## Mathematical base preview versus authoritative accounting EIR

Migration 0061 solves a daily rate directly from the verified signed-contract schedule, using the loan principal as the initial amount and the dated contractual cash flows as the mathematical inputs. For the simple untouched base schedule, a fixed daily coupon plus principal at maturity can mathematically produce the same daily percentage as the operational coupon divided by original principal.

That equality is **informational only**. SPINA does not promote the operational PHP 7-per-PHP 1,000 rule into an authoritative accounting EIR.

The authoritative EIR remains `NULL` because IFRS 9 requires more than a coupon calculation. Before amortised-cost measurement can be used, the accounting policy must support the relevant business-model classification and contractual-cash-flow-characteristics assessment. The EIR calculation also depends on estimated future cash flows through the expected life while considering contractual terms such as prepayment.

## 7x7 issue requiring explicit supported review

The current contract configuration permits partial principal prepayment while the contractual daily-interest amount remains based on **original principal**, rather than declining with partial principal outstanding. Because IFRS 9's amortised-cost/SPPI framework refers to principal and interest on the principal amount outstanding, SPINA does not automatically conclude SPPI for this feature.

This is a review gate, not an automatic failure conclusion. An explicit supported accounting assessment is required before SPINA may select an amortised-cost EIR/carrying policy for 7x7.

The prepayment feature also requires an explicit expected-cash-flow / expected-life policy. The no-prepayment-through-maturity schedule is a useful verified base case but is not automatically the expected cash-flow estimate.

## Readiness states

`accounting.seven_by_seven_eir_carrying_policy_readiness` exposes:

- the operational contractual daily-interest amount and its original-principal ratio;
- the verified base no-prepayment mathematical daily-EIR preview when migration 0060 is ready;
- whether those two base-case rates mathematically match;
- explicit business-model, SPPI, prepayment expected-cash-flow and expected-life review gates;
- `authoritative_daily_eir = NULL`;
- authoritative initial/current gross carrying amounts = `NULL`;
- `eir_policy_ready = false`;
- `carrying_amount_ready = false`;
- `journal_lines_enabled = false`;
- `automatic_source_posting = false`.

For the current configured prepayment feature, a verified base schedule is expected to stop at `sppi_and_prepayment_policy_review_required` until supported policy evidence is approved.

## Safety boundary

Migration 0061 is read-only. It creates a calculation function and views only. It does not create or mutate loans, contract schedules, collection transactions, accounting policy decisions, journal entries, journal lines, or posting history.

The next protected step inside the same Master #296 checkbox is to capture and validate the supported accounting classification and expected-cash-flow/prepayment policy evidence. Only after those gates are resolved may SPINA expose an authoritative 7x7 EIR and carrying amount. Protected preview/identity/draft/posting/reversal remains the following separate Master Checklist item.

## IFRS Foundation references

The design is based on the current IFRS Foundation material for IFRS 9 Financial Instruments: amortised cost requires the relevant hold-to-collect business model and contractual cash flows that are solely payments of principal and interest on the principal amount outstanding. IFRS Interpretations Committee material also explains that the original effective interest rate is calculated from estimated future cash flows at initial recognition and that subsequent cash-flow re-estimation is governed by IFRS 9. IASB's ongoing 2026 Amortised Cost Measurement project is being monitored; tentative future clarifications are not treated as issued requirements in this gate.
