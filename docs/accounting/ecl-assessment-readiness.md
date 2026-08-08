# Stage 5E — Expected Credit Loss assessment readiness

Status: **read-only assessment foundation**. Stage 5E does not quantify or post an expected credit loss yet.

## Purpose

Stage 5E prepares the protected opening-balance cutover for impairment accounting without inventing a credit-loss rate. It consumes the reconciled Stage 5D gross carrying amounts and exposes contractual-arrears backstop indicators for every measured loan.

The accounting Chart of Accounts already reserves:

- `1190 Allowance for Expected Credit Loss` — contra-asset / credit balance.
- `5000 Credit Loss Expense` — expense / debit balance.

Neither account is posted by Stage 5E.

## IFRS/PFRS 9 guardrails used by the design

The ECL model must be probability-weighted, reflect the time value of money, and use reasonable and supportable information available without undue cost or effort, including historical, current and forward-looking information.

For significant increases in credit risk, more than 30 days past due is a rebuttable backstop rather than an automatic bright-line conclusion. For default, IFRS 9 contains a rebuttable presumption that default does not occur later than 90 days past due unless reasonable and supportable information demonstrates that a more lagging criterion is appropriate.

SPINA therefore exposes the 30-day and 90-day values only as **backstop indicators**. They do not automatically assign Stage 2 or Stage 3 and they do not produce an allowance percentage.

## Contractual arrears backstop

For the current level-payment Regular loans and no-cash 7x7 base schedules, Stage 5E determines the oldest unpaid contractual daily due date from cumulative contractual cash due and cumulative actual non-voided cash received through the cutover date.

The resulting `days_past_due_backstop` is used only to display:

- `no_dpd_backstop_trigger`
- `sicr_30dpd_backstop`
- `default_90dpd_backstop`

If Stage 5D has not measured a loan, or a usable level contractual schedule is unavailable, the ECL assessment is blocked for source review rather than guessing a result.

## Why no ECL amount is produced yet

The current test portfolio is not a supportable basis for inventing PD/LGD rates or forward-looking scenario weights. Before a loss allowance is calculated, SPINA still needs an approved policy that documents and evidences at least:

- segmentation of loans with similar credit-risk characteristics;
- historical loss / default experience and data period;
- definition of default and significant increase in credit risk, including qualitative indicators;
- cure and write-off policy;
- recovery expectations and LGD methodology;
- 12-month versus lifetime ECL treatment;
- forward-looking macroeconomic scenarios and probability weights or another supportable method;
- treatment of modifications, renewals, restructurings and collateral/credit enhancements where relevant;
- governance, approval, validation and periodic recalibration.

Until that calibration exists:

- `probability_of_default = NULL`
- `loss_given_default = NULL`
- `forward_looking_multiplier = NULL`
- `ecl_amount = NULL`
- account `1190` has no measurement reference amount
- `ecl_included = false`
- `ready_to_post = false`

## Safety boundary

Stage 5E does not change borrower balances, contractual cash, receipts, remittances, operational delinquency records, workbook proposed amounts, or General Ledger journals. It also does not enable opening-balance posting, automatic source posting, ECL posting, write-off automation, or 7x7 mobile collection.
