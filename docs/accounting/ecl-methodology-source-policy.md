# SPINA V1 ECL methodology and evidence-source policy

Status: **approved methodology boundary; quantitative ECL remains disabled**.

Master tracker: GitHub Issue #296.

## Approved V1 measurement method

SPINA V1 will measure expected credit loss, when the later evidence gates are complete, as a **probability-weighted discounted expected cash shortfall** at loan level.

The measurement must compare contractual cash flows due with cash flows expected to be received, use the applicable **original effective interest rate** for discounting, and reflect:

- an unbiased probability-weighted range of possible outcomes;
- the time value of money; and
- reasonable and supportable information available without undue cost or effort about past events, current conditions, and forecasts of future economic conditions.

This is a cash-shortfall framework. SPINA does **not** require a PD × LGD parameter model for V1 and does not invent a PD, LGD, cure rate, recovery rate, forward-looking multiplier, scenario weight, or management overlay.

Primary IFRS Foundation references:

- IFRS 9 Financial Instruments: https://www.ifrs.org/issued-standards/list-of-standards/ifrs-9-financial-instruments/
- IFRIC Update, September 2022, discussion of IFRS 9 paragraph 5.5.17: https://www.ifrs.org/news-and-events/updates/ifric/2022/ifric-update-september-2022/
- IFRIC Update, March 2019, IFRS 9 definition of credit loss and original-EIR discounting: https://www.ifrs.org/news-and-events/updates/ifric/2019/ifric-update-march-2019/
- IASB Update, October 2013, SICR and the rebuttable 30-DPD backstop: https://media.ifrs.org/2013/IASB/October/IASB-Update-October-2013.html
- IASB Update, September 2013, rebuttable default presumption no later than 90 DPD absent reasonable and supportable evidence for a more lagging criterion: https://media.ifrs.org/2013/IASB/September/IASB-Update-September-2013.html

## 12-month and lifetime boundary

The approved policy keeps the normal IFRS 9 distinction:

- **12-month ECL** applies when the criteria for lifetime ECL are not met.
- **Lifetime ECL** applies after a significant increase in credit risk.
- The existing **30 days past due** indicator is a rebuttable SICR backstop, not an automatic Stage 2 label.
- The existing **90 days past due** indicator is a rebuttable default backstop, not an irreversible automatic default label.

SPINA must not use a purely mechanical DPD-only staging engine. Qualitative and forward-looking evidence belongs in the later protected staging decision.

## Approved evidence source classes

The following source classes may support V1 ECL once each required source is complete and protected:

1. **Verified contractual cash flows** — active immutable verified signed-contract schedules and exact installments.
2. **Original EIR and carrying evidence** — protected original-EIR, initial-measurement and reconciled carrying evidence for the applicable loan path.
3. **Protected collection history** — authoritative collection events and protected posting/reversal history. Mutable summaries are not accounting evidence substitutes.
4. **Contractual DPD and qualitative credit-risk evidence** — contract-driven arrears indicators plus separately evidenced qualitative facts.
5. **Historical loan episodes** — the existing immutable accounting-only historical dataset with source-quality status.
6. **Management-reviewed default outcomes** — the existing immutable protected historical default/non-default review records.
7. **Protected loss/recovery/write-off evidence** — a later controlled workflow for actual loss, recovery, cure and write-off outcomes. Existing nullable historical amount fields are not promoted to authoritative calibration evidence merely because they exist.
8. **Authoritative forward-looking economic evidence** — versioned reasonable-and-supportable external evidence plus Management-approved interpretation. This policy does not choose a variable, forecast, scenario or probability weight by assumption.

## Fail-closed gates after this approval

This policy approval does **not** enable quantitative ECL. Before SPINA can calculate an allowance, the later checklist work must provide at minimum:

- supportable staging/default/write-off/recovery labels and overrides;
- protected loss/recovery evidence for historical outcomes where required;
- reasonable and supportable current/forward-looking evidence;
- exact loan exposure and original-EIR discounting inputs from the protected accounting lifecycle; and
- validation that the resulting cash-shortfall measurement is reproducible and auditable.

Until those gates pass:

- `automatic_staging_enabled = false`;
- `ecl_calculation_enabled = false`;
- `account_1190_posting_enabled = false`;
- `automatic_source_posting = false`;
- no ECL amount may be treated as authoritative.

## Governance

The policy is versioned as `ecl_methodology_v1`. A future change in measurement method, source classes, DPD backstop interpretation, scenario design, or quantitative assumptions requires explicit policy review and regression validation; it must not be introduced as an incidental application default.
