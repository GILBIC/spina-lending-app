# 7x7 / EMER contractual cash-flow readiness

Status: **read-only evidence gate for SPINA V1 Financial Accounting**.

This stage addresses the first 7x7 / EMER accounting item in Master Issue #296: validate the contractual principal-repayment and maturity cash-flow shape before SPINA decides the official PFRS 9 EIR/carrying policy or enables journal posting.

## Authoritative evidence

The source is the loan's active immutable **verified signed-contract schedule**. Product defaults, a loan row, the generic 120-day convention, or operational collection behavior are not sufficient evidence by themselves.

The base greenfield schedule is ready only when the verified signed contract supports all of the following:

- 120 contractual daily periods for the currently configured 7x7 product;
- fixed contractual daily interest of PHP 7 per started PHP 1,000 of original principal;
- daily interest remains based on original principal even if principal can be prepaid;
- the verified no-prepayment-through-maturity schedule carries daily contractual interest on days 1 through maturity;
- full principal is included in the maturity cash flow;
- the exact schedule total equals principal plus the daily contractual interest for the contractual term;
- any populated principal/interest component columns agree with that exact base schedule.

A signed renewal or restructure schedule remains outside this greenfield base gate and requires its own treatment.

## What `ready` means

`pfrs9_contract_cash_flow_ready` means only that the exact verified contractual **base cash-flow shape** is internally supported by signed-contract evidence and the protected 7x7 operational terms.

It does **not** mean that SPINA has concluded:

- the SPPI assessment;
- amortised-cost classification;
- the borrower prepayment expectation used in EIR estimation;
- the official 7x7 EIR;
- the accounting carrying amount;
- journal coordinates, journal lines, or posting.

The contractual prepayment option is deliberately preserved as `prepayment_option_requires_eir_estimate=true`. Estimating expected cash flows under that option belongs to the next Master Checklist item, where the PFRS 9 EIR/carrying policy must be proven separately from the operational PHP 7-per-PHP 1,000 daily-interest rule.

## Safety

This stage creates views only. It does not create, backfill, supersede, or alter signed contracts, loans, collections, accounting journals, or posting history. `journal_lines_enabled=false` and `automatic_source_posting=false` remain mandatory.
