# CB1 Management Mobile Alerts and Audit Visibility Plan

## Goal

Replace the Management dashboard's generic Payment Updates destination with a
permission-filtered, read-only Alerts & Audit center while retaining Payment
Updates as a separate recipient-scoped inbox.

## Implementation order

1. Add backend contract tests for Desktop/Mobile alias parity, canonical
   Management and approved-device enforcement, base permission enforcement,
   independent domain permission reduction, safe 503 behavior, and absence of
   write routes.
2. Add repository tests proving one authoritative projection statement,
   recipient-scoped assigned-remittance counts, owning-record joins, explicit
   audit/source allowlists, no raw audit-detail projection, bounded recent
   history, strict type validation, and fail-closed unknown action/source data.
3. Implement typed backend records, the read-only PostgreSQL projection, one
   shared FastAPI handler, and the hidden Mobile alias. Register the router in
   the existing application only; add no SQL migration.
4. Add failing Flutter tests for strict models, approved-device repository
   headers, compact alert rows, local audit-domain filtering, last-snapshot
   preservation, permission recheck on navigation, and the separate Payment
   Updates destination.
5. Implement the Flutter model/repository/page and route the Management
   dashboard shortcut and unread-activity metric to it. Reuse existing protected
   destinations rather than rebuilding their actions.
6. Run focused backend and Flutter tests, strict Flutter analysis, Python
   compile/Ruff checks, complete backend and Flutter suites, diff/secret checks,
   and the generated-host Android debug/ABI smoke build.
7. Commit only scoped files, push a stacked branch, open a Draft PR against the
   verified Tax Recoverable head, wait for exact-head permanent CI, and update
   Master Issue #296 plus Notion.

## Safety gates

- No production database operation or migration.
- No notification, approval, remittance, custody, accounting, or audit write.
- No free-form audit details returned to Mobile.
- No unknown action/source type admitted to the response.
- No merge, deployment, signing, release, or broad-CB1 completion claim.
- Create State remains paused and Client direct GCash remains the Xendit
  placeholder.
