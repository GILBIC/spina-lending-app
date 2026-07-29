# Calculation regressions Wave 74

Wave 74 protects the lending calculations that are most likely to affect client balances, renewal decisions, and collector reports while moving calculation rules out of the monolithic desktop file.

## Rules covered

1. Regular total-to-pay falls back to principal plus fixed interest when a legacy record stores principal only.
2. Payments before the latest renewal cycle are excluded from the active balance.
3. A renewal preserves the original cycle length and moves the due date to the new cycle.
4. 7x7 payments are allocated to accrued daily interest first and principal second.
5. 7x7 completion percentage uses principal actually paid, not total cash collected.
6. Daily 7x7 interest is fixed at 7 per started thousand of the recorded/current loan principal for the entire loan cycle.
7. Principal payments lower the remaining balance but do not lower the daily-interest basis.
8. Daily interest changes only when the recorded principal is deliberately updated or a new/renewed cycle has a different principal.
9. One effective payment is used per client/date; the latest positive value wins.
10. ADV is shown on covered dates but not on the payment date that funded it.
11. Blank dates not covered by ADV remain PASS candidates.

## Known issue corrected

The dashboard previously subtracted the full 7x7 collection from principal. For a 5,000 principal with a 100 payment on a day carrying 35 interest, it showed principal reduced by 100. Wave 74 records 35 as interest and reduces principal by only 65.

The older statement, report, and renewal-payoff paths also recalculated daily interest from the declining remaining balance. Wave 74 now keeps the original/current recorded principal as the fixed interest basis throughout the same cycle. A 5,000 principal therefore remains 35 daily even after the remaining balance falls below 5,000.

## Automated validation

- compile pure calculation rules and Wave 74 tools
- apply guarded desktop wiring
- compile the updated desktop application
- run pure calculation boundary tests
- verify a 2,000 principal stays at 14 daily after its remaining balance falls below 1,000
- run an in-memory Regular/7x7 dashboard cycle test
- run renewal due-date tests
- run ADV-covered and blank/PASS-candidate day-state tests
- run the existing dashboard regression when available
- run `git diff --check`
- revalidate the exact committed production head on the Windows runner

## Manual validation before merge

- Compare one real Regular client balance with its statement. Completed.
- Confirm a renewed client's due date uses the same cycle length from the newest release date. Completed.
- Confirm the payment day is not labeled ADV while covered dates are. Completed.
- Recheck one real 7x7 client and confirm the daily interest remains based on the recorded principal throughout the same loan cycle.
