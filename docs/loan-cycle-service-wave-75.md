# Loan cycle service Wave 75

Wave 75 continues SPINA modularization by moving reusable loan-cycle timing and completion logic out of the large desktop dashboard function.

## Extracted service

`spina_app/services/loan_cycles.py` now owns:

- payment-start offset normalization
- active release-date selection after renewal
- renewed due-date calculation while preserving the original cycle length
- days-left and elapsed-cycle percentage calculation
- Regular balance and completion finalization
- 7x7 interest-first payment allocation finalization
- dashboard status/priority finalization
- stable dashboard sorting

## Preserved business rules

- Regular legacy totals still normalize to principal plus fixed interest.
- Payments before the current release or renewal cycle remain excluded by the database adapter.
- 7x7 payments still cover daily interest first and principal second.
- 7x7 daily interest remains fixed from the recorded/current loan principal for the whole cycle.
- A renewed loan keeps the original cycle length from the newest release date.
- Dashboard ordering and status labels remain unchanged.

## Boundary

Wave 75 does not move SQL or PostgreSQL compatibility code. `_spina_dashboard_fetch_rows` remains the database adapter and delegates only the reusable timing and finalization rules to the service.

## Automated validation

- compile the service, patch tool, tests, and desktop application
- apply the guarded production patch idempotently
- test renewal timing and zero/one-day payment-start behavior
- test Regular completion finalization
- test 7x7 fixed-principal interest and principal allocation
- verify the monolithic dashboard function delegates to the service
- rerun Wave 74 calculation regressions
- rerun the existing Wave 28 dashboard regression
- run `git diff --check`

## Manual validation before merge

- Open the dashboard and compare one Regular client with its statement.
- Compare one 7x7 client and confirm the balance and fixed daily interest are unchanged from Wave 74.
- Check one renewed client’s latest release, payment-start date, and due date.
- Confirm dashboard rows still appear in the expected priority order.
