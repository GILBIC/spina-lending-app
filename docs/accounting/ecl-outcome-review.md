# Stage 5E.3 — Historical outcome review

Status: **controlled outcome-label review readiness**.

Stage 5E.3 converts the Stage 5E.2 historical dataset into a controlled review queue. It does not classify any historical loan automatically. A management reviewer must explicitly record whether a structurally usable historical episode is default or non-default and must provide an evidence basis, evidence reference, and review note.

## Why review is required

The Stage 5E.2 reconstruction preserves operational evidence such as renewal, archive, deletion, open-at-snapshot status, cash collected, and observed collection days. None of those facts alone proves a PFRS 9 default, cure, write-off, recovery, or non-default outcome.

For example:

- a renewal can be a normal refinance or a settlement with remaining balance;
- an archived loan can have several operational meanings;
- a deleted row is a data/audit event rather than a credit-loss event;
- cash collected equal to or above a contractual amount may be useful evidence, but the system does not use it as an automatic outcome rule.

## Protected workflow

Stage 5E.3 adds:

- permission `accounting.ecl.review` for Management;
- immutable `accounting.ecl_outcome_label_reviews` history;
- protected function `accounting.review_ecl_historical_outcome(...)`;
- `accounting.ecl_outcome_label_review_queue` for evidence review;
- `accounting.ecl_outcome_label_review_summary` for review progress;
- a direct-write guard on `explicit_default_label`.

The protected review function accepts only episodes whose `source_quality_status` is `ready_for_outcome_labeling`. Episodes marked `source_review_required` remain blocked until their structural source issue is separately resolved.

Each review records:

- default or non-default decision;
- evidence basis;
- evidence reference;
- reviewer note;
- reviewer user;
- timestamp;
- review version and superseded review reference.

Corrections do not erase history. A later review creates a new immutable version and updates the episode's current explicit outcome label through the protected function.

## Portfolio gate

Stage 5E.3 also tightens the Stage 5E.2 readiness gate. The historical dataset must not advance merely because one episode has been labeled.

The status remains:

- `outcome_labeling_required` when no structurally usable episodes have been reviewed;
- `outcome_labeling_in_progress` while any structurally usable episode remains unlabeled;
- `default_outcome_data_required` only after all usable episodes are reviewed and none is defaulted;
- `loss_recovery_labeling_required` only after all usable episodes are reviewed and at least one default exists but loss/recovery evidence is still absent;
- `calibration_methodology_required` only after the explicit outcome and loss/recovery prerequisites are satisfied.

## Safety boundary

Stage 5E.3 still does **not**:

- infer a default from renewal, archive, deletion, arrears, or cash totals;
- infer a non-default from cash totals;
- set loss or recovery amounts;
- calculate PD, LGD, cure rates, recovery rates, scenario weights, overlays, or ECL;
- change operational lending balances or collection records;
- populate the protected opening-balance workbook automatically;
- post any General Ledger journal.

Account `1190 Allowance for Expected Credit Loss` therefore remains unquantified and `ready_to_post` remains false.

## Next dependency

After the controlled historical outcome review is substantially complete, the next stage is evidence-backed loss/recovery labeling for reviewed default episodes. Quantitative PD/LGD calibration should remain blocked until the reviewed outcome dataset and loss/recovery dataset are complete enough for an approved methodology.
