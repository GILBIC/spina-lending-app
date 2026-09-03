# CB1 Management Mobile Tax Evidence and Liability Plan

1. Add failing backend contract tests for same-handler mobile aliases and exact
   response filter/page coordinates.
2. Add failing Flutter repository tests for strict tax evidence and liability
   read models, evidence writes, liability prepare/post coordinates, retry
   identities, permission flags, and malformed-response rejection.
3. Add the minimum backend alias/read-response fields; leave every protected
   database function and SQL migration unchanged.
4. Implement strict Flutter models and HTTP repositories.
5. Add compact Management Tax Evidence and Tax Liabilities workspaces, exact
   protected confirmations, and the Financial Accounting launcher.
6. Run focused tests, analyzer/formatter, full Flutter/backend suites, compile
   checks, and a staged-diff audit.
7. Publish a stacked Draft PR only after local verification; wait for exact-head
   CI, then update Master Issue #296 and Notion without completing broad CB1 or
   any human/release gate.
