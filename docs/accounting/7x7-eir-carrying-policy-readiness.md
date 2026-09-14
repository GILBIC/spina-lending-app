# 7x7 / EMER EIR and carrying-policy readiness

Status: **read-only accounting policy gate for Master Issue #296**. This document does not conclude IFRS 9 classification, approve an authoritative EIR, create an amortised-cost carrying amount, or enable accounting posting.

## Why this gate exists

SPINA's operational 7x7 rule is deliberately separate from Financial Accounting measurement:

- contractual daily interest is the configured amount per PHP 1,000 (or started fraction under the approved product rule) of **original principal**;
- partial principal repayment does not reduce that fixed contractual daily-interest amount for a surviving contractual day;
- the exact signed daily payment determines how much principal is amortized underneath each contractual row;
- only the final signed row may be reduced for exact remaining-principal reconciliation;
- approved Extra Principal or full payoff may shorten the operational tail and avoids future unearned contractual interest under the separate servicing rules.

Historical migration 0060 introduced the original contractual-cash-flow evidence gate. Priority #6 migration 0115 corrects that view boundary so the active verified `signed_contract` installment rows themselves are authoritative; product `term_days` no longer reconstructs a separate interest-only/principal-at-maturity schedule.

## Mathematical base preview versus authoritative accounting EIR

Migration 0061 solves a daily rate directly from the verified signed-contract schedule, using the loan principal as the initial amount and the dated contractual cash flows as the mathematical inputs. Priority #6 keeps that exact-schedule solver; it does not introduce a second EIR or schedule engine.

Any mathematical relationship between the contractual fixed-original-principal daily-interest rule and the solved base-case EIR is **informational only**. SPINA does not promote the operational pricing rule into an authoritative accounting EIR by assumption.

The authoritative EIR remains subject to the protected accounting policy/evidence chain because IFRS 9 requires more than a contractual rate calculation. Before amortised-cost measurement can be used, the accounting policy must support the relevant business-model classification and contractual-cash-flow-characteristics assessment. The EIR calculation also depends on estimated future cash flows through the expected life while considering contractual terms such as prepayment.

## 7x7 issue requiring explicit supported review

The current contract design keeps each surviving day's contractual interest based on **original principal**, rather than automatically declining with partial principal outstanding. Because IFRS 9's amortised-cost/SPPI framework refers to principal and interest on the principal amount outstanding, SPINA does not automatically conclude SPPI for this feature.

This is a review gate, not an automatic failure conclusion. An explicit supported accounting assessment is required before SPINA may select an amortised-cost EIR/carrying policy for 7x7.

The prepayment feature also requires an explicit expected-cash-flow / expected-life policy. The exact signed no-prepayment base schedule is a useful verified base case but is not automatically the expected-cash-flow estimate.

## Readiness states

`accounting.seven_by_seven_eir_carrying_policy_readiness` exposes:

- the operational contractual daily-interest amount and its original-principal ratio;
- the verified signed base-schedule mathematical daily-EIR preview when contractual cash-flow readiness is satisfied;
- whether the relevant base-case rates mathematically match where that comparison is meaningful;
- explicit business-model, SPPI, prepayment expected-cash-flow and expected-life review gates;
- `authoritative_daily_eir = NULL`;
- authoritative initial/current gross carrying amounts = `NULL`;
- `eir_policy_ready = false` until the protected evidence chain supports promotion;
- `carrying_amount_ready = false` until the protected evidence chain supports it;
- `journal_lines_enabled = false` at this read-only gate;
- `automatic_source_posting = false`.

The signed contractual duration exposed downstream as `term_days` now follows the exact signed daily schedule count/duration rather than the product default target. This keeps expected-life evidence tied to the same contract that the borrower approved.

## Safety boundary

Migration 0061 is read-only. Priority #6 migration 0115 only replaces the upstream read-only contractual-cash-flow views. Neither creates or mutates loans, contract schedules, collection transactions, accounting policy decisions, journal entries, journal lines, penalties, or posting history.

Pricing/regulatory eligibility remains a separate pre-contract gate. A synthetic schedule used in accounting tests is not an approval of that pricing for a real borrower or regulatory category.

## IFRS Foundation references

The design remains based on IFRS 9 Financial Instruments: amortised cost requires the relevant business model and contractual-cash-flow characteristics, and the effective interest method uses estimated contractual cash flows consistent with the applicable requirements. SPINA therefore preserves exact schedule/evidence versions and keeps business-rule pricing separate from the protected accounting conclusion.
