# 7x7 / EMER contractual cash-flow readiness

Status: **read-only evidence gate for SPINA V1 Financial Accounting**.

This stage addresses the 7x7 / EMER accounting boundary in Master Issue #296: validate the exact signed contractual principal/interest cash-flow shape before SPINA relies on it for PFRS 9 EIR/carrying evidence or enables journal posting.

## Authoritative evidence

The source is the loan's active immutable **verified signed-contract schedule**. Product defaults, a loan row by itself, a generic term convention, or operational collection behavior are not sufficient evidence.

For 7x7, the product `term_days` value is a default/prefill only. The borrower/Management-agreed daily payment determines the generated schedule before signing. Once the exact schedule is approved and signed, its installment rows and last due date define the contractual term and contractual maturity.

The base greenfield schedule is ready only when the verified signed contract supports all of the following:

- daily contractual installment rows beginning on the approved first due date;
- fixed contractual daily interest from the configured amount per started PHP 1,000 of **original principal**;
- the agreed daily payment is greater than that fixed daily interest;
- every normal signed row equals the agreed daily payment and allocates the fixed interest plus principal underneath it;
- only the final signed row may be reduced when required to reconcile the original principal exactly;
- signed principal components reconcile exactly to original principal;
- signed interest components reconcile exactly to fixed daily interest multiplied by the signed installment count;
- the exact signed schedule total equals signed principal plus signed contractual interest;
- the loan-level contractual due date equals the signed schedule's last due date.

Example used for regression only, not as a pricing-law approval: PHP 3,000 principal, PHP 50 agreed daily payment and PHP 21 fixed-original-principal daily interest produces 104 signed rows. Principal totals PHP 3,000, contractual interest totals PHP 2,184, contractual cash flows total PHP 5,184, and contractual maturity is the 104th signed due date even when the product default target is 60 days.

A signed renewal or restructure schedule remains outside this greenfield base gate and requires its own treatment.

## What `ready` means

`pfrs9_contract_cash_flow_ready` means only that the exact verified contractual **base cash-flow shape** is internally supported by signed-contract evidence and reconciles to the authoritative loan-level terms.

It does **not** mean that SPINA has concluded or approved:

- pricing legality or regulatory eligibility;
- a late/nonpayment penalty;
- the SPPI assessment;
- amortised-cost classification;
- the borrower prepayment expectation used in EIR estimation;
- the official 7x7 EIR;
- the accounting carrying amount;
- journal coordinates, journal lines, or posting.

The contractual prepayment option remains `prepayment_option_requires_eir_estimate=true`. Estimating expected cash flows under that option belongs to the protected accounting-policy evidence chain, separate from the operational fixed-original-principal daily-interest rule.

## Contractual versus operational dates

Contractual maturity is the last due date in the immutable signed schedule version. Current Operational Finish may later move under approved servicing rules such as borrower-caused extensions or Management No Collection, but those operational changes do not silently rewrite the signed contractual maturity.

The accounting readiness gate fails closed when the loan-level `due_date` does not match the signed contractual maturity. Priority #6 separately needs contract-lock synchronization so `lending.loans.daily_amount` and `due_date` cannot remain stale after Management approves different 7x7 terms.

## Safety

This stage creates/replaces read-only accounting views only. It does not create, backfill, supersede, or alter signed contracts, loans, collections, accounting journals, penalties, or posting history. `journal_lines_enabled=false` and `automatic_source_posting=false` remain mandatory.
