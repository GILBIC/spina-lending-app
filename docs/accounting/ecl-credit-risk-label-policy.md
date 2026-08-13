# SPINA V1 ECL credit-risk label policy

Status: **protected labels enabled for Management review; quantitative ECL remains disabled**.

Master tracker: GitHub Issue #296.

## Purpose

This stage implements evidence-backed classification labels needed before SPINA can quantify expected credit loss. It does not calculate an allowance, post account `1190`, or execute a loan write-off.

The protected labels are:

- `stage_1_12_month` — 12-month ECL measurement category when lifetime-ECL criteria are not met;
- `stage_2_lifetime` — lifetime ECL after a supported significant increase in credit risk;
- `stage_3_credit_impaired` — credit-impaired state supported by evidence;
- explicit reviewed default / non-default;
- `supported_no_reasonable_expectation_of_recovery` — a write-off-support conclusion only, not the accounting write-off itself;
- `cash_recovery_observed` — an exact later protected positive collection after a prior default / Stage 3 / write-off-support review; and
- `cured` — a separately evidenced reviewed improvement from a prior default / Stage 3 / write-off-support state.

## DPD backstops are not automatic labels

The existing contract-driven DPD foundation remains the starting evidence source. It does not become an automatic staging engine.

- More than 30 days past due remains a **rebuttable SICR backstop**. A Stage 1 conclusion at or beyond the backstop requires separate rebuttal evidence and rationale.
- The 90-days-past-due default boundary remains a **rebuttable default backstop**. A non-default conclusion at or beyond that backstop requires separate rebuttal evidence and rationale.
- Qualitative or other evidence may support Stage 2, Stage 3 or default before those DPD backstops. Contractual DPD alone cannot do so before the corresponding backstop.
- Contractual DPD alone also cannot rebut a DPD backstop.

Primary IFRS Foundation / IASB references:

- IFRS 9 Financial Instruments: https://www.ifrs.org/issued-standards/list-of-standards/ifrs-9-financial-instruments/
- IASB Update, October 2013 — SICR assessment and the rebuttable 30-DPD presumption: https://media.ifrs.org/2013/IASB/October/IASB-Update-October-2013.html
- IASB Update, September 2013 — rebuttable default presumption no later than 90 DPD absent reasonable and supportable evidence for a more lagging criterion: https://media.ifrs.org/2013/IASB/September/IASB-Update-September-2013.html

## Write-off support is not write-off execution

SPINA records only a protected **write-off-support label** in this stage. The label requires Stage 3, reviewed default, separate evidence and rationale that Management has no reasonable expectation of recovery. The system does not reduce the gross carrying amount and does not create a derecognition journal in this stage.

The accounting execution remains a later controlled item because it must be tied to authoritative carrying amount, allowance treatment, exact journal coordinates and immutable audit.

The write-off criterion is consistent with IFRS 9 paragraph 5.4.4 as reproduced in the Australian Accounting Standards Board's IFRS-equivalent AASB 9 text: https://standards.aasb.gov.au/aasb-9-sep-2020

## Recovery and cure

Recovery and cure are intentionally separate:

- `cash_recovery_observed` requires the exact same-loan, non-voided, positive protected payment/advance transaction occurring after a prior reviewed default / Stage 3 / write-off-support state.
- Recovery chronology uses the protected collection transaction's authoritative server `accepted_at` timestamp. It must be **strictly later** than the prior deteriorated review's `created_at`; sharing the same calendar date is not enough and intraday order is never inferred from `collection_date` alone.
- `cured` requires a prior reviewed deteriorated state plus a new explicit non-default review that is no longer Stage 3 and is supported by evidence other than DPD alone.
- Neither label is generated automatically from a balance, loan status, renewal, archive event or elapsed time.

The IFRS Interpretations Committee has explicitly discussed financial assets that later become paid in full or no longer credit-impaired and the related reversal of ECL. See:

- IFRIC Update, November 2018: https://www.ifrs.org/news-and-events/updates/ifric/2018/ifric-update-november-2018/
- Curing of a credit-impaired financial asset project: https://www.ifrs.org/projects/completed-projects/2019/curing-of-a-credit-impaired-financial-asset-ifrs-9/

This stage records the evidence label only. It does not calculate or post an impairment reversal.

## Stale-review protection

Every review snapshots the authoritative active contract schedule and the current DPD evidence band:

- `current`
- `past_due_1_29`
- `past_due_30_89`
- `past_due_90_plus`

A review becomes stale and requires refresh when the active schedule/version changes or when DPD crosses one of those evidence boundaries. A review is not rewritten merely because DPD changes by one day inside the same evidence band.

Corrections and later decisions are new immutable review versions; prior versions are retained through `supersedes_review_id`.

## Fail-closed boundary

Until the later ECL checklist items are completed:

- `automatic_staging_enabled = false`;
- `automatic_default_enabled = false`;
- `automatic_write_off_enabled = false`;
- `automatic_recovery_enabled = false`;
- `quantitative_ecl_ready = false`;
- `ecl_calculation_enabled = false`;
- `account_1190_posting_enabled = false`;
- `automatic_source_posting = false`.

No numeric PD, LGD, cure rate, recovery rate, scenario weight, management overlay or ECL amount is introduced by this label stage.
