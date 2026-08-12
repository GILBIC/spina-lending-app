# 7x7 / EMER classification and expected-cash-flow policy evidence

Status: **protected Management-reviewed accounting-policy evidence gate inside Master Issue #296**. This layer records supported conclusions; it does not itself promote a mathematical rate into an authoritative EIR, establish carrying amounts, or enable journal posting.

## Purpose

Migration 0061 deliberately separated the operational PHP 7-per-PHP 1,000 original-principal rule from a mathematical no-prepayment daily-EIR preview. Migration 0062 adds the next evidence boundary: Management must explicitly document the classification and expected-cash-flow policy before a later accounting-measurement layer may use any 7x7 EIR or carrying amount.

The system never treats a mathematical match between the operational rate and the verified base-schedule EIR preview as an accounting-policy conclusion.

## Classification evidence

IFRS 9 classifies a financial asset using both the entity's business model for managing the asset and the contractual cash-flow characteristics of the instrument. The protected decision therefore requires explicit evidence for:

- business model: `held_to_collect`, `held_to_collect_and_sell`, or `other`;
- contractual cash-flow / SPPI conclusion: `passes` or `fails`;
- resulting measurement category: `amortised_cost`, `fvoci`, or `fvpl`;
- a non-empty classification assessment, policy reference, rationale, and supporting evidence reference.

The database enforces category consistency. A `held_to_collect` + SPPI-pass decision maps to amortised cost; `held_to_collect_and_sell` + SPPI-pass maps to FVOCI; an `other` business model or SPPI-fail decision maps to FVPL. SPINA does not pick one of these conclusions automatically.

## Expected-life and prepayment evidence

The current 7x7 contract can permit principal prepayment while contractual daily interest remains based on original principal. Because this feature affects the cash-flow pattern used for effective-interest measurement, Migration 0062 requires an explicit expected-cash-flow policy rather than assuming that the no-prepayment maturity schedule is always the expected estimate.

Management must choose, with evidence, one of two states:

- `verified_no_prepayment_schedule_is_expected_cash_flow_estimate`; or
- `separate_expected_prepayment_cash_flow_evidence_required`.

Expected life is also explicit: either the contractual term or a supported shorter expected life. A shorter life cannot be entered without a shorter evidence-backed day count.

If separate prepayment cash-flow evidence is required, SPINA remains blocked at `expected_prepayment_cash_flow_evidence_required`. It does not manufacture prepayment probabilities, timing, or amounts.

## Stale-safe review identity

`accounting.seven_by_seven_policy_review_token(loan_id)` hashes the exact current verified contract/EIR-readiness snapshot. The protected decision function accepts only the current token. An exact retry returns the existing decision; materially different evidence requires an explicit void before correction.

Direct INSERT/UPDATE/DELETE of decision or void evidence is blocked by immutable guards. Only an active actor with the Management permission `accounting.7x7_classification_policy.manage` may record or void the evidence.

## What becomes ready—and what does not

A current Management decision can establish that the business-model, SPPI and expected-cash-flow policy reviews have been concluded. For the narrow evidence combination of held-to-collect + SPPI pass + amortised cost + contractual expected life + evidence that the verified no-prepayment schedule is the expected cash-flow estimate, the view may expose `classification_policy_evidence_ready_for_eir_promotion = true`.

That flag means **ready for the next protected EIR-promotion review**, not that an EIR is already authoritative. Migration 0062 still forces:

- `authoritative_daily_eir = NULL`;
- authoritative initial/current gross carrying amount = `NULL`;
- `eir_policy_ready = false`;
- `carrying_amount_ready = false`;
- `journal_lines_enabled = false`;
- `automatic_source_posting = false`.

FVPL and FVOCI conclusions intentionally route to separate accounting-measurement design rather than being forced through the amortised-cost path.

## Live-install safety

The migration installs permissions, protected evidence tables/functions and read-only status/summary views. Installation does not create a Management policy decision, loan or contract row, collection history, journal entry, journal line, posting, authoritative EIR, or carrying amount. Existing evidence is preserved on rerun.

The dedicated disposable PostgreSQL proof exercises Management authorization, category consistency, exact retry idempotency, immutability, explicit void-before-correction, and the fail-closed prepayment-evidence path before the live installer is allowed to run after merge.

## IFRS Foundation basis

The current IFRS Foundation IFRS 9 materials state that financial-asset classification depends on the entity's business model and the asset's contractual cash-flow characteristics. Amortised cost requires both a hold-to-collect business model and contractual cash flows that are solely payments of principal and interest on the principal amount outstanding; a hold-to-collect-and-sell model with qualifying contractual cash flows leads to FVOCI, while assets outside those conditions are measured at FVPL. IFRS 9 also contains specific requirements and amendments concerning prepayment features.

SPINA therefore captures the conclusions and their supporting evidence explicitly and fails closed when evidence is incomplete. It does not substitute the operational 7x7 pricing rule for the accounting analysis.