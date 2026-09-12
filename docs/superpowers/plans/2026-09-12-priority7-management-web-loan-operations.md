# Priority #7 Management Web Loan Operations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only Management Web Loan Operations surface that renders the existing protected FastAPI/PostgreSQL monitoring payload without introducing financial mutation or duplicate business logic.

**Architecture:** The Web uses the existing `GET /api/v1/management/loan-operations` endpoint and renders only server-returned summary/entry/audit values. A focused module owns loading, markup, and section-local filtering. `roles/management.js` receives only the minimal integration hooks, while the server remains the authorization and financial authority.

**Tech Stack:** Vanilla ES modules, Node 22 `node:test`, existing SPINA Web UI helpers, FastAPI/PostgreSQL API contract.

**Spec:** `docs/superpowers/specs/2026-09-12-priority7-management-web-loan-operations-design.md`

## Global Constraints

- Backend/PostgreSQL remains authoritative.
- Reuse `GET /api/v1/management/loan-operations`.
- Do not invent a permission: the existing backend contract is Management-role-only.
- No collection/remittance/correction/void mutation in this slice.
- No local lending, allocation, schedule, accounting, or balance calculation.
- Do not change Priority #4, Priority #6, or Priority #8 business rules.
- Keep `management.js` integration additive and narrow because Priority #5 PR #422 also modifies that file.
- No merge, deployment, production Auth/data mutation, or live financial action.

---

### Task 1: Management role action contract

**Files:**
- Modify: `spina_portal/assets/roles.js`
- Create: `spina_portal/tests/management-loan-operations.test.mjs`

**Interfaces:**
- Consumes: `availableRoleActions(role, permissions)`.
- Produces: Management action key `management-loan-operations`, path `/api/v1/management/loan-operations`, section `Operations`, with no `permission` field.

- [ ] **Step 1: Write the failing test**

Test that Management receives the Loan Operations action even with an empty permission list, while Employee and Collector never receive the path. Assert the action has no `permission` property so Web does not invent authorization not present in FastAPI.

- [ ] **Step 2: Run exact PR CI to verify RED**

Expected: portal test lane fails only because `management-loan-operations` is absent; existing portal tests remain Green.

- [ ] **Step 3: Write minimal implementation**

Add one `action(...)` entry under `ROLE_ENDPOINTS.management`:

```js
action('management-loan-operations', 'Loan operations', '/api/v1/management/loan-operations', {
  section: 'Operations',
}),
```

- [ ] **Step 4: Run exact-head CI and verify the focused test passes**

Expected: new role-action test Green.

### Task 2: Read-only loader and renderer

**Files:**
- Create: `spina_portal/assets/management-loan-operations.js`
- Modify: `spina_portal/tests/management-loan-operations.test.mjs`

**Interfaces:**
- Produces: `loadManagementLoanOperations(api, { query = '', status = 'all' } = {})`.
- Produces: `managementLoanOperationsMarkup(payload)`.
- Produces: `bindManagementLoanOperations(context)` for section-local search/filter reload.

- [ ] **Step 1: Write failing loader/renderer tests**

Require the loader to call only `/api/v1/management/loan-operations?q=<encoded>&status=<encoded>`. Use deliberately inconsistent summary/entry amounts in the fixture and assert rendered output displays exact server totals/official balances rather than recomputing them. Assert server notice, audit reason, receipt, Collector and status are visible and escaped.

- [ ] **Step 2: Verify RED on exact-head CI**

Expected: only the new module contract fails because the module/functions are absent.

- [ ] **Step 3: Implement the minimum module**

Use existing `asArray`, `badge`, `emptyState`, `errorCard`, `escapeHtml`, `formatDate`, `formatDateTime`, `formatMoney`, `loadingPanel`, and `metricCard` helpers. Do not sum or derive financial values.

`bindManagementLoanOperations(context)` binds `#management-loan-operations-search`, reloads `#management-loan-operations-results`, and renders server data/errors without remounting the whole Management workspace.

- [ ] **Step 4: Verify focused tests Green**

Expected: role action, loader, renderer, and section-local filtering tests pass.

### Task 3: Management workspace integration

**Files:**
- Modify: `spina_portal/assets/roles/management.js`
- Modify: `spina_portal/tests/management-loan-operations.test.mjs`

**Interfaces:**
- Consumes: `loadManagementLoanOperations`, `managementLoanOperationsMarkup`, `bindManagementLoanOperations`.
- Produces: Management navigation id `management-loan-operations` and one read-only section.

- [ ] **Step 1: Write failing integration test**

Read `roles/management.js` as source and require the isolated module import, navigation id, initial loader call, rendered section id, and binding call. Do not require a new permission check.

- [ ] **Step 2: Verify exact-head RED**

Expected: only the missing integration assertion fails while module behavior stays Green.

- [ ] **Step 3: Apply minimal integration**

Add the module import; add `Loan operations` after `Clients & loans`; include the initial `loadManagementLoanOperations(api)` request in the existing `Promise.all`; render the section with error handling; call `bindManagementLoanOperations(context)` after DOM render.

- [ ] **Step 4: Verify portal syntax/tests/build Green**

Expected: all portal checks pass.

### Task 4: Installed Web/PWA dependency integrity

**Files:**
- Modify: `spina_portal/sw.js`
- Modify: `spina_portal/tests/management-loan-operations.test.mjs`

**Interfaces:**
- Consumes: static import from `roles/management.js`.
- Produces: `/assets/management-loan-operations.js` in `SHELL_ASSETS`.

- [ ] **Step 1: Write failing shell-cache test**

Require the new static module path in `spina_portal/sw.js`.

- [ ] **Step 2: Verify RED**

Expected: one PWA dependency assertion fails.

- [ ] **Step 3: Add the single shell-cache entry**

Do not change API caching or service-worker routing policy.

- [ ] **Step 4: Verify full exact-head SPINA CI**

Require success in all three lanes: Backend/quality/security; Portal/Flutter/Android; Financial/disposable PostgreSQL.

### Task 5: Continuity checkpoint

**Files:**
- Update PR #425 body/checkpoint.
- Update Notion `Spina Current Project State — Company Release Build`.
- Update Create State.

- [ ] Record exact branch, PR, final head, task, RED heads/runs, final Green CI run, conflict note, and next safe Priority #7 action.
- [ ] Leave PR Draft/open/unmerged and perform no deployment or production mutation.
