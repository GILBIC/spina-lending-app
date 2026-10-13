# Current-cutoff credit-risk review

Management can retain an explicit Stage 1, Stage 2 or Stage 3 risk decision from
the elapsed-assessment screen. The screen shows the actual Manila business date,
the active signed schedule, days past due, unpaid amount and prior review. Stage,
default, write-off-support, recovery and evidence choices start blank.

A continuing modified loan retains its predecessor's impairment history. The
review context distinguishes a review on the selected operational loan
(`prior_review`) from the exact inherited review (`inherited_review`, including
the predecessor loan ID). The private source digest binds the inherited review
and immutable renewal lineage. Neither a renewal nor an empty current-review
form supplies an automatic cure; Management must retain an explicit supported
current decision.

The selected fiscal period must be open and end on the actual current business
date. A caller cannot supply a review date, reviewer, days-past-due figure or
source snapshot. Historical labels require actual retained dated evidence;
this workflow cannot manufacture it.

The backend binds the decision to the configured book and a digest of the
current loan, schedule, operational overlays, protected payments/allocations,
DPD calculation and prior review. Confirmation rechecks current Management
permission and source facts under locks, then delegates label policy to the
existing protected credit-risk review function. DPD backstops remain rebuttable
only with the required separate evidence; the screen does not choose a stage.

An unchanged request may recover the same retained review after a lost response.
Changed input, changed source, a superseding review or revoked current authority
cannot reuse that result. The binding and review are immutable. An actual change
requires reloading the source and retaining a new version.

This action retains a risk decision. Preparing expected-credit-loss scenarios,
reviewing the measured amount and posting an assessment remain separate steps.
Write-off support is a label and does not execute a write-off.

The web and mobile endpoints are:
- GET/POST `/management/financial-accounting/period-elapsed-assessments/{period_id}/loans/{loan_id}/risk-review`,
  under their existing `/api/v1` and `/api/mobile/v1` prefixes.
- Reading requires `accounting.view`; retaining requires
  `accounting.ecl.credit_risk_label.review`, with active Management membership
  checked in the API and database.

Responses use `Cache-Control: no-store` and an explicit small projection.
Private source snapshots, borrower detail, receipt payloads, evidence references,
reviewer identifiers and review notes do not appear in the context response.
Migration 0171 keeps the evidence table and functions outside direct client
and service-role grants.
