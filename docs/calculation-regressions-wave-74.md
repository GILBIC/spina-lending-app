# Calculation regressions Wave 74

Wave 74 protects the lending calculations that are most likely to affect client balances, renewal decisions, and collector reports while continuing SPINA modularization.

## Rules covered

1. Regular total-to-pay falls back to principal plus fixed interest when a legacy record stores principal only.
2. Payments before the latest renewal cycle are excluded from the active balance.
3. A renewal preserves the original cycle length and moves the due date to the new cycle.
4. 7x7 payments are allocated to accrued daily interest first and principal second.
5. 7x7 completion percentage uses principal actually paid, not total cash collected.
6. Daily 7x7 interest is fixed from the recorded/current loan principal for the entire loan cycle.
7. Principal payments reduce the balance but do not lower the daily-interest basis.
8. The daily interest changes only when the principal is deliberately updated or a renewed cycle uses a different principal.
9. One effective payment is used per client/date; the latest positive value wins.
10. ADV is shown on covered dates but not on the payment date that funded it.
11. Blank dates not covered by ADV remain PASS candidates.

## Confirmed 7x7 examples

- ₱1,000 principal = ₱7 daily interest.
- ₱2,000 principal = ₱14 daily interest.
- ₱5,000 principal = ₱35 daily interest throughout the same loan cycle, even after the remaining principal falls below ₱5,000.

## Known issue corrected

The dashboard previously subtracted the full 7x7 collection from principal. For a ₱5,000 principal with a ₱100 payment on a day carrying ₱35 interest, Wave 74 records ₱35 as interest and reduces principal by only ₱65. The ₱35 daily-interest amount remains fixed for that loan cycle.

## Automated validation

- compiled pure calculation rules and Wave 74 tools
- applied guarded desktop wiring across all identified calculation paths
- compiled the updated desktop application
- passed pure calculation and boundary tests
- passed fixed-principal 7x7 tests, including a balance falling below its original bracket
- passed in-memory Regular/7x7 dashboard cycle tests
- passed renewal due-date tests
- passed ADV-covered and blank/PASS-candidate day-state tests
- passed the existing dashboard regression
- passed `git diff --check`
- revalidated the exact committed production head on Windows

## Manual validation before merge

- [x] Compare one real Regular client balance with its statement.
- [ ] Recheck one real 7x7 client and confirm the daily interest stays fixed from the recorded principal as the balance decreases.
- [x] Confirm a renewed client's due date uses the same cycle length from the newest release date.
- [x] Open a month with ADV coverage and confirm the payment day is not labeled ADV while covered dates are.
