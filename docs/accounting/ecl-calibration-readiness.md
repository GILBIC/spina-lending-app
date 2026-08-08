# Stage 5E.1 — ECL historical calibration readiness

Status: **source-readiness only**. Stage 5E.1 does not calculate or post an expected credit loss.

## Why this stage exists

Stage 5E established mechanical arrears backstops and deliberately left PD, LGD, forward-looking adjustments, ECL amount, and account 1190 unquantified. Stage 5E.1 now checks whether SPINA has enough historical outcome evidence to support a loss calibration instead of treating the current test portfolio as a historical loss model.

IFRS/PFRS 9 requires ECL estimates to use reasonable and supportable information about past events, current conditions and forecasts of future economic conditions. The 30-day and 90-day past-due values remain rebuttable backstops; they are not substitutes for a calibrated loss model.

## Readiness inventory

The database view `accounting.ecl_calibration_source_inventory` reports:

- total, active, resolved (`paid`/`closed`) and defaulted loan counts;
- earliest/latest loan release dates;
- valid non-voided cash-collection count and observation dates;
- whether mature outcome history exists;
- whether default/loss outcome history exists;
- whether a dedicated recovery/write-off history source exists;
- the resulting calibration-readiness status and blockers.

No minimum sample size, PD percentage, LGD percentage, cure rate, recovery rate, macroeconomic multiplier, or scenario weight is invented in this stage.

## Current cutover implication

If the live database contains only recent active/test loans and no resolved/defaulted history, Stage 5E.1 reports `historical_data_required`. That is a control result, not an error.

The next data step is to migrate or otherwise provide an approved historical loan-outcome dataset covering completed loans, defaults, recoveries/write-offs and collection history. Only after that source is reconciled can SPINA derive and validate historical loss rates and then add current/forward-looking adjustments.

## Safety boundary

Stage 5E.1 does not:

- assign ECL stages automatically;
- calculate PD or LGD;
- calculate an ECL amount;
- populate account 1190;
- modify borrower balances or collection records;
- verify opening-workbook lines;
- post opening balances or credit-loss journals;
- enable automatic accounting posting; or
- enable 7x7 mobile collection.
