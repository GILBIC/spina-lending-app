# CB1 Management Mobile Tax Evidence and Liability

Status: approved bounded implementation slice under Master Issue #296. This
extends the existing A6.2 FastAPI/PostgreSQL tax-evidence and protected
tax-liability workflows to Gilbic Mobile. It creates no second tax calculator,
General Journal, or accounting authority.

## Current authority

- `v1_tax_evidence_api.py` and the PostgreSQL A6.2 evidence/readiness views are
  authoritative for approved rule evidence, per-loan DST evidence, and exact
  per-transaction percentage-tax allocation evidence.
- `v1_tax_liability_api.py` and the protected database functions are
  authoritative for tax-liability preparation and posting.
- The database derives readiness, blockers, source coordinates, fiscal period,
  journal identity, accounts, and posting state. Mobile must not reproduce the
  DST calculation or use PFRS/EIR interest as a tax base.

## Mobile behavior in this slice

- Add `/api/mobile/v1/...` aliases to the existing tax-evidence and
  tax-liability handlers. Include the exact request filter/page coordinates in
  each read response; no SQL or protected database function changes are needed.
- Add a Management Tax Accounting launcher under Financial Accounting, with
  separate Tax Evidence and Tax Liabilities workspaces.
- Tax Evidence shows the server summary, approved immutable rules, DST source
  readiness, percentage-tax source readiness, exact blockers, and intersected
  permissions.
- Management may record a rule, DST evidence, or percentage allocation only
  from retained evidence and an explicit protected review. DST/percentage forms
  are opened from an exact server row and carry its immutable source
  coordinates; supersession references the current evidence when present.
- Percentage evidence must reconcile taxable receipt plus principal exactly to
  the server source-cash amount before any request is sent.
- Tax Liabilities shows the authoritative summary/queue and supports protected
  prepare/post only for exact actionable items with current server and session
  permissions. Posting confirms evidence digest, tax due, both accounts,
  recognition date, fiscal period, and prepared journal identity.
- Evidence requests reuse one RFC 4122 UUID while the unchanged snapshot is
  retried. Liability posting reuses one 64-character lowercase hexadecimal
  confirmation token while the unchanged prepared snapshot is retried.
- Every confirmed success reloads authoritative state. An uncertain result is
  never treated as success and retains the retry identity.

## Fail-closed rules

- Management role, approved device, and action permissions remain enforced by
  the existing backend handlers. Flutter also intersects current session and
  server permissions before showing an action.
- Mobile accepts only the two backend tax types and exact server statuses.
- Mobile does not calculate a legal rate, DST amount, percentage-tax base, tax
  liability, posting date, fiscal period, journal line, account, or balance.
- Policy flags must prove evidence-backed readiness/protected liability is
  enabled and `automatic_source_posting=false`. Evidence readiness must keep
  `tax_posting_enabled=false`; liability posting must keep the existing
  settlement/correction controls enabled.
- Posted records are immutable/read-only. Blocked and stale records show the
  exact safe server blocker.

## Explicit boundaries

- No migration, live tax rule/evidence/return/payment, production journal,
  legal interpretation, tax-rate invention, automatic posting, merge,
  deployment, signing, or release.
- Settlement, decrease/reversal, upward amendment/additional payment,
  recoverable refund/credit, financial notifications, and generalized audit
  visibility remain separate bounded CB1 slices.
- Human Android/iOS acceptance remains deferred and unchecked.
