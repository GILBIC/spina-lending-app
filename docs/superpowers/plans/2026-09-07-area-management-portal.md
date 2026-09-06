# Area Management Staff/Management Portal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give authorized Employee/Office Staff and Management a simple two-panel Area Management screen for building the City/Municipality → Barangay → unlimited Subarea hierarchy, ordering routes, assigning Collectors, moving Clients, and safely retiring/reactivating Areas.

**Architecture:** Build one shared Portal Area-management module used by both Employee and Management role workspaces. The UI is only a server-authorized client: all tree state, effective Collector ownership, Client transfer timing, conflict detection, and retirement rules come from Plan 1 APIs. The left panel renders the expandable/searchable hierarchy; the right panel renders the selected node, effective/inherited Collector, counts, and permitted actions. Do not duplicate the same feature in `employee.js` and `management.js`.

**Tech Stack:** Existing `spina_portal` vanilla ES modules/DOM, existing `api.js` request wrapper, existing `ui.js` helpers, Node 22 test runner, existing `app.css`, backend APIs from `2026-09-07-area-management-server-authority.md`.

**Spec:** `docs/superpowers/specs/2026-09-06-area-management-design.md`

## Dependencies

- Plan 1 server authority must be implemented and Green before this plan begins.
- Rebase the Portal implementation branch onto the exact Plan 1 Green head so tests exercise the real API contract.
- Do not bypass missing API behavior with client-side fake ownership rules.

## Global Constraints

- Employee/Office Staff and Management share the same Area Management component.
- UI visibility follows server session permissions, but the server remains the security boundary.
- `area.manage` enables normal create/rename/move/reorder.
- `area.collector.assign` enables Collector assignment/removal.
- `area.client.assign` enables Client search/transfer.
- `area.retire` enables retire/reactivate; only Management should receive it from the server.
- Never infer `Management` power only from a JavaScript role string when the exact server permission is absent.
- Root managed node label = **City/Municipality**.
- Direct child of a managed City = **Barangay**.
- Any deeper node = **Subarea**. Do not show `Subarea 1`, `Subarea 2`, etc.
- Legacy unmapped roots must be visibly marked as legacy/unmapped and must not be falsely labeled City/Municipality.
- Search must support Area name/path and Collector name without destroying the hierarchy context.
- Manual route order is authoritative and saved through the server. Do not sort alphabetically after a server order is received.
- Moving a branch uses server preview first, then one explicit confirmation, then mutation.
- Client transfer uses server preview first so the UI shows Immediate vs Next Collection Day determined by SPINA; user never selects timing manually.
- Retirement/reactivation uses server preview/conflict response; do not offer a destructive delete action.
- Full Client address, ID/Meralco evidence, location photo, and sensitive KYC evidence are outside this screen.
- No production deployment or merge without explicit Management approval.
- Strict TDD for every behavior change.

---

### Task 1: Create a shared Area tree view model and pure rendering helpers

**Files:**
- Create: `spina_portal/assets/area-management.js`
- Create: `spina_portal/tests/area-management.test.mjs`

**Interfaces:**
- `buildAreaTree(nodes)` converts the server’s ordered flat Area records into nested render nodes without re-sorting siblings.
- `areaKindLabel(node, parent)` returns `City/Municipality`, `Barangay`, `Subarea`, or `Legacy unmapped area`.
- `filterAreaTree(tree, query)` keeps matching nodes plus ancestors/descendants needed for context.
- `renderAreaManagementShell(state)` returns the two-panel HTML string.
- No API calls in these pure helpers.

- [ ] **Step 1: Write RED pure-function tests**

Use server-like fixtures:

```js
const nodes = [
  { area_uid: 'cardona', parent_area_uid: null, name: 'Cardona', depth: 0, sort_order: 0, is_legacy_unmapped: false },
  { area_uid: 'calahan', parent_area_uid: 'cardona', name: 'Calahan', depth: 1, sort_order: 0, is_legacy_unmapped: false },
  { area_uid: 'balayong', parent_area_uid: 'calahan', name: 'Balayong', depth: 2, sort_order: 0, is_legacy_unmapped: false },
  { area_uid: 'nia', parent_area_uid: 'calahan', name: 'NIA', depth: 2, sort_order: 1, is_legacy_unmapped: false },
];
```

Prove:

- order remains Balayong → NIA exactly as server supplied;
- arbitrary depth works with a 7-level fixture;
- `Calahan` is Barangay, `Balayong` and all deeper descendants are Subarea;
- a legacy root is labeled `Legacy unmapped area`;
- search `NIA` preserves Cardona/Calahan ancestor context;
- search by Collector name preserves matching branch;
- no fixed-depth array indexing exists.

- [ ] **Step 2: Run RED**

```bash
cd spina_portal
node --test tests/area-management.test.mjs
```

Expected: module import failure.

- [ ] **Step 3: Implement pure helpers in `area-management.js`**

Build children by `parent_area_uid`, preserving incoming order. Do not call `.sort()` unless the API contract explicitly returns unordered data; Plan 1 returns route order already.

Use escaped text for every server field through existing `escapeHtml()`.

- [ ] **Step 4: Run GREEN**

```bash
cd spina_portal
node --test tests/area-management.test.mjs
```

- [ ] **Step 5: Commit**

```bash
git add spina_portal/assets/area-management.js spina_portal/tests/area-management.test.mjs
git commit -m "feat: add Area tree portal model"
```

---

### Task 2: Load Area state and render the approved two-panel screen

**Files:**
- Modify: `spina_portal/assets/area-management.js`
- Modify: `spina_portal/tests/area-management.test.mjs`
- Modify: `spina_portal/assets/app.css`

**Interfaces:**
- `mountAreaManagement(context)` loads `/api/v1/areas` and `/api/v1/areas/collectors` as permitted.
- Left panel: search, expandable tree, route order, effective Collector context.
- Right panel: selected Area path/state, explicit vs inherited Collector, direct/subtree Client counts, child count, action buttons allowed by session permissions.
- Local UI state: selected node UID, expanded UID set, search query, loading/error state.

- [ ] **Step 1: Add RED DOM/render tests**

Test rendered HTML for:

```text
AREA MANAGEMENT
Search area / Collector
Cardona
  Calahan — Collector A
    Balayong
    NIA — Collector B
```

The selected Balayong details must show:

- path `Cardona › Calahan › Balayong`;
- `Effective Collector: Collector A`;
- `Inherited from: Calahan` when the API marks the source as ancestor;
- direct Client count, subtree Client count, child count;
- active/inactive badge.

Prove the normal screen never contains ID/Meralco/source-address labels or photo markup.

- [ ] **Step 2: Run RED**

```bash
cd spina_portal
node --test tests/area-management.test.mjs
```

- [ ] **Step 3: Implement stateful mount**

Use existing `settledRequest`, `loadingPanel`, `errorCard`, `hasPermission`, `badge`, `showToast`, and `setButtonBusy` helpers.

Fetch reads in parallel:

```js
const [areasResult, collectorsResult] = await Promise.all([
  settledRequest(api, '/api/v1/areas', {}, { areas: [] }),
  canAssignCollector
    ? settledRequest(api, '/api/v1/areas/collectors', {}, { collectors: [] })
    : Promise.resolve({ data: { collectors: [] }, error: null }),
]);
```

Do not reload the entire Employee/Management workspace for every tree expand/collapse. Re-render only the Area module from local state; reload server data only after a mutation.

- [ ] **Step 4: Add responsive CSS**

Add narrowly scoped classes such as:

- `.area-management`
- `.area-tree-panel`
- `.area-details-panel`
- `.area-tree-row`
- `.area-tree-children`
- `.area-route-order-controls`

Desktop: two columns. Narrow/mobile browser: stack tree above details. Reuse existing spacing/buttons/cards; do not introduce a parallel design system.

- [ ] **Step 5: Run GREEN + portal checks**

```bash
cd spina_portal
node --test tests/area-management.test.mjs
npm run check:portal
```

- [ ] **Step 6: Commit**

```bash
git add spina_portal/assets/area-management.js spina_portal/assets/app.css spina_portal/tests/area-management.test.mjs
git commit -m "feat: render shared Area Management portal"
```

---

### Task 3: Connect Area Management into Employee and Management workspaces

**Files:**
- Modify: `spina_portal/assets/roles/employee.js`
- Modify: `spina_portal/assets/roles/management.js`
- Modify: `spina_portal/assets/area-management.js`
- Modify: `spina_portal/tests/area-management.test.mjs`
- Modify existing role tests if present under: `spina_portal/tests/`

**Interfaces:**
- Employee navigation includes `Area Management` only when at least one Area permission is present.
- Management navigation uses the same shared module.
- No duplicated Area HTML/action code in role files.

- [ ] **Step 1: Add RED role-mount tests**

Prove:

- Employee with `area.manage` sees Area Management.
- Employee with only unrelated permissions does not.
- Management with Area permissions sees the same component contract.
- Management with `area.retire` receives retirement controls from the shared module; Employee without it does not.
- Role modules do not create their own `fetch('/api/v1/areas...')` implementation outside the shared module.

- [ ] **Step 2: Run RED**

```bash
cd spina_portal
npm run test:portal
```

- [ ] **Step 3: Add shared navigation/mount hook**

In both role modules import the shared module:

```js
import { mountAreaManagement } from '../area-management.js';
```

Add the navigation item only when:

```js
const canUseAreaManagement = [
  'area.manage',
  'area.collector.assign',
  'area.client.assign',
  'area.retire',
].some((permission) => hasPermission(session, permission));
```

Render a dedicated section container and call `mountAreaManagement({ ...context, root: areaRoot })` after the role’s base workspace HTML exists.

Do not call `mountEmployeeWorkspace()`/`mountManagementWorkspace()` recursively from Area action callbacks.

- [ ] **Step 4: Run GREEN**

```bash
cd spina_portal
npm run test:portal
npm run check:portal
```

- [ ] **Step 5: Commit**

```bash
git add spina_portal/assets/roles/employee.js spina_portal/assets/roles/management.js spina_portal/assets/area-management.js spina_portal/tests
git commit -m "feat: connect Area Management to staff roles"
```

---

### Task 4: Implement create/rename and context-correct child labels

**Files:**
- Modify: `spina_portal/assets/area-management.js`
- Modify: `spina_portal/tests/area-management.test.mjs`

**Interfaces:**
- Root action: `+ Add City/Municipality`.
- Selected managed City: `+ Add Barangay`.
- Selected Barangay or deeper node: `+ Add Subarea`.
- Legacy unmapped node does not pretend to have an official type until placed/classified by move.
- Create uses `POST /api/v1/areas`.
- Rename uses `PATCH /api/v1/areas/{area_id}`.

- [ ] **Step 1: Add RED action-label and request tests**

Prove:

- root create sends `{ parent_area_id: null, name }`;
- City child sends City UID and button says `Add Barangay`;
- deeper child always says `Add Subarea` no matter how deep;
- blank name is rejected in UI before request;
- server 409 conflict is shown and prior tree remains on screen;
- successful mutation reloads authoritative tree and preserves selected node when it still exists.

- [ ] **Step 2: Run RED**

```bash
cd spina_portal
node --test tests/area-management.test.mjs
```

- [ ] **Step 3: Implement compact forms/dialogs**

Use inline card/dialog UI consistent with existing Portal forms. Never request full path manually; the user types only the node name and parent is selected from tree context.

- [ ] **Step 4: Run GREEN**

```bash
cd spina_portal
node --test tests/area-management.test.mjs
```

- [ ] **Step 5: Commit**

```bash
git add spina_portal/assets/area-management.js spina_portal/tests/area-management.test.mjs
git commit -m "feat: add Area create and rename controls"
```

---

### Task 5: Implement manual route ordering with drag plus reliable Up/Down fallback

**Files:**
- Modify: `spina_portal/assets/area-management.js`
- Modify: `spina_portal/assets/app.css`
- Modify: `spina_portal/tests/area-management.test.mjs`

**Interfaces:**
- Sibling order only; drag cannot move a node into a different parent.
- Up/Down buttons work without drag support.
- Save calls `POST /api/v1/areas/reorder` with complete ordered sibling UIDs.
- Server response becomes new truth.

- [ ] **Step 1: Add RED ordering tests**

With siblings `Balayong, NIA, Main Calahan` prove:

- Down on Balayong yields `NIA, Balayong, Main Calahan` request order.
- Up on Main Calahan yields `Balayong, Main Calahan, NIA` from original state.
- first Up and last Down are disabled.
- drag reorder changes only siblings under the same parent.
- no `.sort((a,b) => a.name...)` alphabetical fallback overrides the saved order.

- [ ] **Step 2: Run RED**

```bash
cd spina_portal
node --test tests/area-management.test.mjs
```

- [ ] **Step 3: Implement Up/Down first**

Make Up/Down the authoritative accessible fallback and cover it completely with tests.

- [ ] **Step 4: Add HTML5 drag enhancement**

Drag only updates local sibling ordering, then submits the same reorder API payload as Up/Down. If drag is unsupported, Up/Down remains fully functional.

- [ ] **Step 5: Run GREEN**

```bash
cd spina_portal
node --test tests/area-management.test.mjs
npm run check:portal
```

- [ ] **Step 6: Commit**

```bash
git add spina_portal/assets/area-management.js spina_portal/assets/app.css spina_portal/tests/area-management.test.mjs
git commit -m "feat: add manual Area route ordering"
```

---

### Task 6: Implement Collector assignment with inherited-owner clarity

**Files:**
- Modify: `spina_portal/assets/area-management.js`
- Modify: `spina_portal/tests/area-management.test.mjs`

**Interfaces:**
- Explicit assignment selector shows active Collectors from server.
- Details distinguish:
  - `Explicit: Collector B`
  - `Inherited: Collector A from Calahan`
  - `Unassigned`
  - `Conflict — SPINA requires Staff review`
- Save uses `PUT /api/v1/areas/{area_id}/collector`.
- Remove exact override uses `DELETE /api/v1/areas/{area_id}/collector` and then displays inherited fallback returned by server.

- [ ] **Step 1: Add RED assignment tests**

Prove the Calahan/NIA example:

1. Calahan explicit A.
2. NIA initially inherited A.
3. Assign NIA to B → NIA explicit B.
4. Remove NIA explicit assignment → NIA inherited A again.
5. Calahan assignment remains untouched.
6. Parent/child ownership logic is never calculated client-side beyond displaying server fields.

- [ ] **Step 2: Run RED**

```bash
cd spina_portal
node --test tests/area-management.test.mjs
```

- [ ] **Step 3: Implement assignment UI**

Before save, show one concise explanation:

```text
Collector B will handle NIA and its descendants unless a deeper Subarea has its own Collector override.
```

Do not enumerate or mutate descendant assignments.

- [ ] **Step 4: Run GREEN**

```bash
cd spina_portal
node --test tests/area-management.test.mjs
```

- [ ] **Step 5: Commit**

```bash
git add spina_portal/assets/area-management.js spina_portal/tests/area-management.test.mjs
git commit -m "feat: manage inherited Collector Area ownership"
```

---

### Task 7: Implement branch move preview and confirmation

**Files:**
- Modify: `spina_portal/assets/area-management.js`
- Modify: `spina_portal/tests/area-management.test.mjs`

**Interfaces:**
- Choose a new parent from active valid Areas.
- Fetch `GET /api/v1/areas/{area_id}/move-preview?new_parent_area_id=...` before confirmation.
- Preview shows affected Clients, descendant Areas, effective Collector changes, and stale delegation warning if server returns one.
- Confirm once; then `POST /api/v1/areas/{area_id}/move`.

- [ ] **Step 1: Add RED preview tests**

Prove no move POST occurs until preview succeeds and user confirms.

Use preview fixture:

```json
{
  "clients_affected": 23,
  "descendant_areas_affected": 4,
  "effective_collector_before": "Collector A",
  "effective_collector_after": "Collector C",
  "stale_delegated_access_count": 1
}
```

Assert these facts appear before Confirm.

- [ ] **Step 2: Run RED**

```bash
cd spina_portal
node --test tests/area-management.test.mjs
```

- [ ] **Step 3: Implement move workflow**

Do not allow selecting self/descendants if tree state can identify them, but still rely on server rejection for final protection.

- [ ] **Step 4: Run GREEN**

```bash
cd spina_portal
node --test tests/area-management.test.mjs
```

- [ ] **Step 5: Commit**

```bash
git add spina_portal/assets/area-management.js spina_portal/tests/area-management.test.mjs
git commit -m "feat: add safe Area branch move workflow"
```

---

### Task 8: Implement Client search and automatic-timing Area transfer

**Files:**
- Modify: `spina_portal/assets/area-management.js`
- Modify: `spina_portal/tests/area-management.test.mjs`

**Interfaces:**
- Client search uses `GET /api/v1/areas/clients?q=...`.
- Transfer preview uses `GET /api/v1/clients/{client_id}/area-transfer-preview?target_area_id=...`.
- Submit uses `POST /api/v1/clients/{client_id}/area-transfer`.
- Staff/Management never chooses Immediate/Tomorrow manually.

- [ ] **Step 1: Add RED Client-transfer tests**

Prove preview rendering for both server decisions:

```text
Effective: Immediately — no official collection has been recorded today.
```

and:

```text
Effective: Sep 8, 2026 — next scheduled collection day because today already has an official collection.
```

Also prove:

- Client shows one explicit current Area path;
- ancestor membership is display-only and not submitted as multiple assignments;
- API conflict `client_transfer_next_collection_day_unavailable` is shown as a clear message with no guessed date;
- successful deferred transfer shows `Scheduled` and retains the current Area until effective date.

- [ ] **Step 2: Run RED**

```bash
cd spina_portal
node --test tests/area-management.test.mjs
```

- [ ] **Step 3: Implement Client transfer panel**

Keep search results operationally minimal: Client name/code, current Area, effective Collector. Do not request/render ID/Meralco/KYC evidence.

- [ ] **Step 4: Run GREEN**

```bash
cd spina_portal
node --test tests/area-management.test.mjs
```

- [ ] **Step 5: Commit**

```bash
git add spina_portal/assets/area-management.js spina_portal/tests/area-management.test.mjs
git commit -m "feat: add automatic Client Area transfer UI"
```

---

### Task 9: Implement Management-only retirement/reactivation UI

**Files:**
- Modify: `spina_portal/assets/area-management.js`
- Modify: `spina_portal/tests/area-management.test.mjs`

**Interfaces:**
- Render Retire/Reactivate only when `hasPermission(session, 'area.retire')`.
- Retirement preview uses `GET /api/v1/areas/{area_id}/retirement-preview`.
- Retire uses `POST /api/v1/areas/{area_id}/retire`.
- Reactivate uses `POST /api/v1/areas/{area_id}/reactivate`.
- Never render a hard Delete action.

- [ ] **Step 1: Add RED authority/dependency tests**

Prove:

- Employee with normal Area permissions has no Retire/Reactivate buttons.
- Management session with `area.retire` sees them.
- retirement with `clients_affected > 0`, active Collector assignments, or pending transfers shows blockers and does not submit.
- clear Area can be retired after confirmation.
- retired Area remains visible when server returns it with inactive state.

- [ ] **Step 2: Run RED**

```bash
cd spina_portal
node --test tests/area-management.test.mjs
```

- [ ] **Step 3: Implement lifecycle controls**

Use warning styling and explicit wording `Retire Area`; never `Delete Area`.

- [ ] **Step 4: Run GREEN**

```bash
cd spina_portal
node --test tests/area-management.test.mjs
```

- [ ] **Step 5: Commit**

```bash
git add spina_portal/assets/area-management.js spina_portal/tests/area-management.test.mjs
git commit -m "feat: add Management Area retirement controls"
```

---

### Task 10: Portal regression and exact-head verification

**Files:**
- No product changes unless a test exposes a real bug.

- [ ] **Step 1: Run focused Area tests**

```bash
cd spina_portal
node --test tests/area-management.test.mjs
```

- [ ] **Step 2: Run complete Portal tests and static checks**

```bash
cd spina_portal
npm run test:portal
npm run check:portal
```

- [ ] **Step 3: Run repository-level Portal command used by CI**

From repository root run the current CI-equivalent Portal check, preserving Node 22 requirements.

- [ ] **Step 4: Manual synthetic browser acceptance with fake/test data only**

Verify:

1. Cardona → Calahan → Balayong → deeper nesting expands cleanly.
2. Search can find a deep Subarea and preserve ancestor context.
3. Route order persists after refresh.
4. Employee can normal-manage but cannot retire.
5. Management can retire only a dependency-free node.
6. NIA child Collector override displays explicit B while parent Calahan remains A.
7. Removing NIA override displays inherited A again.
8. Client transfer preview never exposes a manual timing choice.
9. No KYC/address/photo data appears in Area Management.

- [ ] **Step 5: Push and use exact-head CI shorthand**

Report the exact implementation head to Management and wait for **Red** / **Green**. Inspect exact-head CI once when reported; no continuous polling.

## Completion boundary

Plan 2 is complete when the shared Staff/Management Portal Area screen is Green and uses only Plan 1 server authority. It does not redesign the Collector Flutter route; that is Plan 3.
