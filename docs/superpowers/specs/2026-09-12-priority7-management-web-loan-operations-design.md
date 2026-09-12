# Priority #7 Management Web Loan Operations Design

## Goal

Expose the existing server-authoritative Management Loan Operations monitoring capability in the shared SPINA Web application without adding another collection, remittance, correction, void, schedule, or accounting path.

## Authority boundary

- PostgreSQL/FastAPI remains authoritative.
- Reuse existing `GET /api/v1/management/loan-operations` only.
- The existing endpoint authenticates the device/session and requires the server-side `management` role.
- The endpoint does not define a separate permission string. Web must not invent one.
- Web role/navigation visibility is presentation only; direct unauthorized requests still fail server-side.
- Web performs no financial mutation in this slice.
- Web does not recalculate balances, collection totals, remittance totals, correction counts, void counts, allocation, schedules, or accounting values.

## Web surface

Add one Management-only read-only section called **Loan operations**.

The section shows the authoritative server payload:

- latest collection date and amount;
- latest payment / unable-to-pay counts;
- unremitted amount and entry count;
- pending remittance amount and count;
- received remittance amount and count;
- correction and void counts;
- collection activity rows including receipt, Client, loan, loan type, Collector, entry type, amount, official balance, covered dates, status, remittance number, and void reason where returned;
- correction / void audit events including time, receipt, Client/loan, actor, event type, and reason;
- the server-provided notice.

## Filtering

Use only the backend's existing query contract:

- `q` — free-text search;
- `status` — `all`, `unremitted`, `submitted`, `received`, or `voided`.

Changing the search/status reloads only the Loan Operations section through the existing endpoint. No local financial filtering or derived totals are authoritative.

## UI/UX

- Reuse existing SPINA cards, metric grid, table wrapper, badges, money/date helpers, loading panel, and error card.
- Keep the screen responsive through existing grid/table overflow behavior; avoid new global CSS unless a demonstrated layout defect requires it.
- Use clear read-only copy. Do not imply that this screen performs corrections, voids, remittance acceptance, or direct payment entry.

## Files

- Add `spina_portal/assets/management-loan-operations.js` for endpoint loading, markup, and section-local search/status binding.
- Add `spina_portal/tests/management-loan-operations.test.mjs` for strict-TDD behavior.
- Modify `spina_portal/assets/roles.js` only to expose a Management-only role action with no invented permission.
- Modify `spina_portal/assets/roles/management.js` only for the minimal import/navigation/initial-load/section integration.
- Modify `spina_portal/sw.js` only to precache the new static module.

## Parallel-development constraints

- Do not touch Priority #4 onboarding/CIF/first-loan files or rules.
- Do not touch Priority #6 7x7 contract/accounting rules.
- Priority #5 PR #422 also has additive `management.js` integration. Keep this slice isolated so later reconciliation remains small.
- Priority #8 Client schedule work must remain independent; no Client files are modified here.

## Explicit non-goals

- no backend change;
- no database migration;
- no new permission or RBAC rule;
- no Direct Payment Entry UI;
- no collection correction/void mutation UI;
- no remittance mutation UI;
- no local schedule/allocation/accounting engine;
- no merge, deployment, production Auth/data mutation, or live financial action.
