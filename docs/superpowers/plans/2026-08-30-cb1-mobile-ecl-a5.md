# CB1 protected ECL adjustments implementation plan

1. Add failing backend contract tests for complete mobile A5 read coordinates and recovery-review discovery.
2. Enrich the existing A5 repository/API payload from authoritative PostgreSQL records. Keep every write routed to the existing protected functions.
3. Add failing Flutter contract/repository tests for strict queue parsing, exact request bodies, permissions, receipts, and fail-closed behavior.
4. Implement typed A5 models and the mobile repository.
5. Add failing widget and launcher tests for filters, permission intersection, confirmations, evidence input, stable retries, and authoritative reload.
6. Implement the Management ECL Adjustments page, Financial Accounting launcher, and mutation-surface inventory entry.
7. Format and run focused backend/Flutter tests, static analysis, full backend and Flutter suites, and diff review.
8. Commit and push the bounded branch, open a stacked Draft PR, wait for exact-head CI, then update GitHub Master Issue #296 and Notion. Keep the broad CB1 checkbox open and distinguish implemented from released behavior.
