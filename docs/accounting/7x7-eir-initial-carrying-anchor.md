# 7x7 original-EIR and initial-carrying anchor

## Master checklist scope

This control continues the unchecked **7x7 EIR/carrying policy** item in Master Issue #296. It is intentionally separate from the later 7x7 preview/identity/draft/posting/reversal lifecycle.

The operational PHP 7-per-PHP 1,000 daily-interest rule is a product/contract rule. It is not promoted into accounting merely because a mathematical base EIR preview can equal that operational rate.

## Accounting basis

IFRS 9 classifies a financial asset using the business model and contractual cash-flow characteristics. For a supported amortised-cost path, the asset is held to collect contractual cash flows and those contractual cash flows pass the SPPI assessment. At initial recognition, IFRS 9 measures a financial asset at fair value plus directly attributable transaction costs when the asset is not measured at fair value through profit or loss. The effective-interest method then uses the financial instrument's expected cash flows and initial measurement to calculate amortised cost and allocate interest revenue.

Primary references:

- IFRS Foundation — IFRS 9 Financial Instruments: https://www.ifrs.org/issued-standards/list-of-standards/ifrs-9-financial-instruments/
- IFRS Foundation / IFRIC — Presentation of interest revenue for particular financial instruments: https://www.ifrs.org/projects/completed-projects/2018/presentation-of-interest-revenue-for-particular-financial-instruments-ifrs-9-and-ias-1/tentative-agenda-decision-presentation-of-interest-revenue-for-particular-financial-instruments/

## Protected promotion boundary

Migration `0063_add_7x7_eir_initial_carrying_anchor.sql` adds an immutable Management-reviewed anchor that requires all of the following before original EIR can become authoritative for the supported V1 amortised-cost path:

1. Current Stage 0062 classification-policy evidence is still active and exact.
2. Business model is explicitly `held_to_collect`.
3. SPPI conclusion is explicitly `passes`.
4. Measurement category is `amortised_cost`.
5. Management's expected-cash-flow policy explicitly uses the verified no-prepayment signed-contract schedule as the expected-cash-flow estimate.
6. Expected life is explicitly the contractual term for this narrow V1 path.
7. Management supplies a substantive, evidence-backed IFRS 9 initial gross carrying amount and an assessment covering fair value, directly attributable transaction costs, integral fees/points, and the supporting source documents.
8. The protected function recomputes original daily EIR from the exact verified signed-contract schedule using that exact initial gross carrying amount.

The system, not Management, solves the promoted EIR. Management does not type an authoritative EIR into the anchor.

## Why this proves separation from the operational rate

The stored anchor keeps both the principal-based mathematical preview and the authoritative EIR solved from the evidence-backed initial carrying amount. If the evidence-backed initial carrying amount differs from principal, the authoritative EIR can differ from the operational PHP 7-per-PHP 1,000 rate even though the principal-based mathematical preview equals that operational rate.

This prevents accidental use of the operational allocator as an accounting measurement shortcut.

## Fail-closed boundary

This slice deliberately does **not** create or enable:

- an authoritative current gross carrying amount after collections;
- a 7x7 source-event identity;
- journal coordinates;
- journal drafts;
- posting or reversal;
- automatic source posting.

`authoritative_current_gross_carrying_amount` remains `NULL`, `current_carrying_amount_ready=false`, `carrying_amount_ready=false`, `journal_lines_enabled=false`, and `automatic_source_posting=false`.

The later protected 7x7 accounting lifecycle must reconcile actual source cash and posted ledger history back to this immutable original-EIR / initial-carrying anchor before a current carrying amount can become authoritative.
