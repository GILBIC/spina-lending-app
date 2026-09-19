# Office application draft entry

Continue approved Task 3 from verified `767ea779` as one implementation and
verification batch. Use the existing create/append APIs without new schema,
pricing, confirmation, approval or financial mutations.

- Protected Client-scoped GET `loan-applications/entry-context` returns current
  eligible CIF identity/version plus active catalog product id/code/name only.
  Reuse persisted office authorization and the existing source-eligibility
  check. Unknown/ineligible source returns generic 409; handled responses are
  no-store. Context is advisory; existing transactional save checks remain.
- Employee/Management application reference selection gains New application
  and Edit application information actions. Preserve the read-only lookup.
- Standalone editor captures every request, repayment and obligation field;
  blank is null, obligations are unknown/yes/no, money remains decimal text.
  Permit incomplete drafts. Product choices use server labels and IDs; preserve
  an existing unavailable product without silently clearing it.
- Create with selected Client/CIF/reference. Append with exact application ID
  and expected saved version. If current CIF changed, require explicit selection
  of the new source; never silently overlay historical data or reuse evidence.
- One save at a time. Retain edits after 400/422. Stale/uncertain/malformed save
  outcomes lock saving until explicit authoritative reload. Never auto-retry or
  invent a new application reference. Clear sensitive data after access denial.
- Clear/invalidate pending reads and writes on reference change, Clear, remount,
  disposal and logout. After save read the authoritative application summary.
- Preserve existing CIF/Area/report features, permissions and base records.

Verify context API and real PostgreSQL authorization/eligibility/catalog/read-only
behavior; editor and workspace create/append payloads, exact money, stale/uncertain
results and lifecycle cleanup; actual desktop/mobile browser forms and build.
Publish complete batch, inspect matching CI, update GitHub/Notion/local handoff.
PR420 remains Draft/open/unmerged and Priority4 remains43% until all Task3 passes.
Protected acknowledgment/fullT01/privacy and final approval/release remain open.

## Verification

- 174 application API regressions passed, including 20 entry-context cases.
- 329 real PostgreSQL tests passed, including 23 new context cases; disposable
  database cleanup and zero leftovers verified, scratch PostgreSQL stopped.
- 353 portal tests passed, including 48 editor and 14 workspace cases; syntax
  valid for 60 modules.
- Edge Employee desktop and Management mobile forms passed exact create/append,
  explicit changed-CIF selection, stale reload/Cancel and pending-save logout.
- Review found Cancel after an uncertain write could skip reconciliation for a
  new application. Fixed: pending or uncertain writes request authoritative
  reload on Cancel as well; ordinary pre-save cancellation stays unchanged.
- Portal build/source checks and independent review passed. Full published-head
  CI remains the acceptance gate after publication.
