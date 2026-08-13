# ECL Read-Only Quantitative Measurement Policy

## Scope

This is the frozen SPINA V1 Master #296 **A3** calculation boundary. It permits a protected Management-reviewed quantitative ECL measurement only after the A1+A2 evidence gate is fully ready. It creates an immutable calculation/audit snapshot only.

It does **not** post `1190 Allowance for Expected Credit Loss`, create a journal, execute a write-off, or enable automatic source posting.

## Approved calculation method

SPINA uses the approved loan-level **probability-weighted discounted expected-cash-shortfall** method. It does not substitute an invented PD × LGD model.

For each explicitly supported scenario:

1. take the exact remaining contractual cash flows from the current immutable verified contract schedule and protected payment allocations;
2. discount those contractual cash flows to the measurement date using the applicable protected **original daily EIR**;
3. discount the scenario's explicitly Management-approved expected cash receipts to the same measurement date using the same original EIR;
4. calculate the scenario cash-shortfall PV as the non-negative difference between those two present values;
5. multiply that shortfall by the scenario's explicit evidence-supported probability; and
6. sum the probability-weighted scenario shortfalls, then round only the final authoritative ECL amount to currency-cent precision.

The stored snapshot retains the higher-precision contractual PV, scenario expected-cash-flow PVs, scenario shortfall PVs and weighted shortfall before the final currency-cent amount.

## Stage horizon

- `stage_1_12_month` → **12-month ECL**.
- `stage_2_lifetime` → **lifetime ECL**.
- `stage_3_credit_impaired` → **lifetime ECL**.

For Stage 1, 12 months is the **credit-loss/default-event horizon**, not a mechanical truncation of contractual cash flows at day 365. Expected cash receipts may continue across the remaining contractual life when evaluating losses associated with default events possible within the 12-month horizon.

## Scenario evidence boundary

SPINA does not create a probability, multiplier, overlay, PD, LGD, cure rate or recovery rate merely to make ECL run.

Every scenario must contain:

- a stable scenario key;
- an explicit probability with no more than 12 decimal places;
- retained evidence reference and substantive Management rationale;
- one or more exact forward-looking evidence IDs that are current and approved for a new measurement; and
- explicit expected cash-receipt dates and currency-cent amounts, or an explicitly empty expected-cash-flow array when no receipts are expected in that scenario.

At least two scenarios are required and their probabilities must sum exactly to `1.000000000000`. Free-text notes cannot clear the A1+A2 readiness gate and cannot silently supply missing numeric assumptions.

## Authoritative input snapshot

A measurement pins, at minimum:

- loan and measurement date;
- exact verified schedule ID/version and contract reference;
- exact current ECL label review ID/version and stage;
- exact original-EIR source key/policy and original daily EIR;
- protected initial gross carrying anchor;
- exact approved forward-looking evidence IDs;
- all A1+A2 readiness flags;
- exact contractual installment, allocation and remaining-cash-flow snapshot;
- normalized scenario probabilities and expected cash flows;
- discount basis and rounding policy; and
- a SHA-256 calculation digest over the normalized protected inputs and result.

Measurements are immutable and versioned. An exact retry returns the existing measurement rather than creating a duplicate. A changed calculation creates a new immutable version.

## Current-date boundary

SPINA V1 A3 measures the **current authoritative date only**. Backdated reconstruction is intentionally fail-closed because it would require historical reconstruction of every schedule, label, posting, reversal and economic-evidence state. Historical reproducibility comes from the immutable snapshot and digest of the measurement that was actually performed on the authoritative date.

## Forward-looking period hardening

A forward-looking evidence version cannot satisfy readiness before both its Management effective date **and** its stated forecast-period start. Stale, superseded or revoked evidence cannot support a new measurement. Supersession never rewrites a prior measurement snapshot.

## Rounding and repeatability

All discounting and probability weighting use PostgreSQL `NUMERIC` high precision. Expected receipt inputs must be exact currency cents. Scenario probabilities are exact to at most 12 decimal places. Intermediate PVs are retained to 12 decimal places and the final ECL is rounded once to currency cents.

The same normalized inputs must produce the same calculation digest and exact retry ID.

## Posting boundary

The A3 queue exposes an authoritative ECL amount only for a fully ready loan with a current read-only measurement matching the exact schedule and credit-risk review snapshot. Blocked or incomplete loans expose `NULL` as the authoritative ECL amount.

`account_1190_posting_enabled=false` and `automatic_source_posting=false` remain mandatory throughout A3. Protected allowance posting is a separate A4 stage.