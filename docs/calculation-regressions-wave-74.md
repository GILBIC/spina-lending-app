# Calculation regressions Wave 74

Wave 74 protects the lending calculations that are most likely to affect client balances, renewal decisions, and collector reports.

## Rules covered

1. Regular total-to-pay falls back to principal plus fixed interest when a legacy record stores principal only.
2. Payments before the latest renewal cycle are excluded from the active balance.
3. A renewal preserves the original cycle length and moves the due date to the new cycle.
4. 7x7 payments are allocated to accrued daily interest first and principal second.
5. 7x7 completion percentage uses principal actually paid, not total cash collected.
6. Daily 7x7 interest remains 7 per started thousand of remaining principal until the principal crosses a bracket boundary.
7. One effective payment is used per client/date; the latest positive value wins.
8. ADV is shown on covered dates but not on the payment date that funded it.
9. Blank dates not covered by ADV remain PASS candidates.

## Known issue corrected

The dashboard previously subtracted the full 7x7 collection from principal. For a 5,000 principal with a 100 payment on a day carrying 35 interest, it showed principal reduced by 100. Wave 74 records 35 as interest and reduces principal by only 65.

## Automated validation

- compile pure calculation rules and Wave 74 tools
- apply guarded desktop wiring
- compile the updated desktop application
- run pure calculation boundary tests
- run an in-memory Regular/7x7 dashboard cycle test
- run renewal due-date tests
- run ADV-covered and blank/PASS-candidate day-state tests
- run the existing dashboard regression when available
- run `git diff --check`

## Manual validation before merge

- Compare one real Regular client balance with its statement.
- Compare one 7x7 client after at least two payments and confirm only the principal portions reduce the displayed balance.
- Confirm a renewed client's due date uses the same cycle length from the newest release date.
- Open a month with ADV coverage and confirm the payment day is not labeled ADV while covered dates are.
