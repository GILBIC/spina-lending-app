# Area Management Collector Mobile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Collector phone follow the approved City/Municipality → Barangay → unlimited Subarea route hierarchy, keep the daily ledger compact, and expose approved Client Tools such as read-only schedule and verified collection-location details without creating a second routing or schedule engine.

**Architecture:** Extend the existing authenticated Collector route payload with stable Area-node metadata from Plan 1 while preserving legacy `areas` and `entry.area` compatibility. Flutter builds a read-only hierarchy from server-provided ordered nodes and keeps all payment allocation/posting on the existing protected flows. Client Tools are an on-demand detail surface: existing payment/correction/renewal actions remain authoritative, schedule uses the existing `/collector/loans/{loan_id}/schedule` endpoint, and collection-location data is read from a new route-scoped server detail endpoint only after the server proves the Collector currently owns or is delegated that Client path.

**Tech Stack:** Existing FastAPI/psycopg backend, existing `collector_route_repository.py`, existing `collector_schedule_api.py`, Flutter/Dart, current `CollectorRoutePage`, `collector_client_ledger.dart`, existing route cache, existing protected payment/correction/renewal flows, Flutter test.

**Spec:** `docs/superpowers/specs/2026-09-06-area-management-design.md`

## Scope decomposition

This is **Plan 3 of 3** for Priority #5.

- Plan 1 — `2026-09-07-area-management-server-authority.md`: PostgreSQL/FastAPI Area authority, ownership, transfer timing, retirement, and route compatibility.
- Plan 2 — `2026-09-07-area-management-portal.md`: Staff/Management Web/PC Area tree and actions.
- Plan 3 — this file: Collector hierarchy navigation, compact route rows, hidden Client Tools, read-only schedule, and verified collection-location details.

Plan 3 starts only after the relevant Plan 1 server contract is Green. Do not fake hierarchy or ownership in Flutter when the server contract is absent.

## Global Constraints

- Rebase the mobile implementation branch onto the exact Green head of Plan 1 before starting.
- No production deployment, live Client/photo upload, production DB/Auth mutation, merge, or release without explicit Management approval.
- The Collector cannot create, rename, move, reorder, retire, reactivate, assign, or reassign permanent Areas.
- The phone never computes permanent Collector ownership. It renders only the route already filtered by the server.
- Parent assignment + child override stays server-authoritative; the parent Collector must not receive an overridden child branch.
- Preserve current one-tap Regular/7x7 combined payment, detailed payment, unable-to-pay, correction, remittance/custody, renewal, and offline safety behavior.
- The normal route remains a compact digital daily ledger. Do not render full address, ID/Meralco source data, residential/business evidence, or location photo in the normal Client row.
- Hierarchy has no fixed Subarea depth. Flutter code must not assume exactly City + Barangay + one Subarea.
- Manual Area order from the server is authoritative. Do not alphabetically re-sort siblings.
- Offline cached route remains read-only for financial writes. Hierarchy metadata may be cached with the route, but stale cache must never widen access.
- Client Schedule is read-only and must reuse the existing authoritative Collector schedule endpoint/engine.
- Collection-location details are route-scoped and read-only in this plan. No mobile location-edit/upload flow is introduced here.
- If no authoritative collection-location record exists yet, show `Collection location not yet verified` rather than inventing an address/photo.
- Strict TDD for each behavior change.

---

### Task 1: Extend the Collector route server contract with stable ordered Area hierarchy metadata

**Files:**
- Modify: `gilbic_backend/src/gilbic_backend/collector_route_repository.py`
- Modify: `gilbic_backend/src/gilbic_backend/collector_route_api.py`
- Modify: `gilbic_backend/tests/test_collector_route_repository.py`
- Modify or create focused API test under: `gilbic_backend/tests/test_collector_route_api.py`

**Interfaces:**
- Existing response fields remain: `areas`, `entries`, `entry.area`.
- Add `area_nodes`: ordered route-relevant node records only.
- Add `area_uid` to each route entry when available.
- `area_nodes` fields:
  - `area_uid`
  - `parent_area_uid`
  - `name`
  - `full_path`
  - `depth`
  - `sort_order`
  - `is_legacy_unmapped`
- The returned tree includes only nodes needed to render the authenticated Collector's effective route plus required ancestors for context.
- It must not leak an overridden child branch owned by another Collector.

- [ ] **Step 1: Write RED repository/API tests**

Create fixtures:

```text
Cardona
  Calahan -> Collector A
    Balayong -> inherited A
      Mabini St. -> inherited A
    NIA -> Collector B
```

Request Collector A's route and prove:

- `area_nodes` contains Cardona, Calahan, Balayong, Mabini St.;
- `area_nodes` does **not** contain NIA when no Client/route context for A remains there;
- a Client at Mabini St. carries its stable `area_uid`;
- sibling order follows `area_nodes.sort_order` from Plan 1, not `lower(name)`;
- legacy route entries without `area_uid` still return their existing text path and do not crash;
- existing route payment/readiness fields remain unchanged.

- [ ] **Step 2: Run RED**

```bash
python -m pytest \
  gilbic_backend/tests/test_collector_route_repository.py \
  gilbic_backend/tests/test_collector_route_api.py -q
```

Expected: new assertions fail because hierarchy metadata is absent.

- [ ] **Step 3: Implement the minimum route metadata reader**

Use `lending.area_nodes` and the existing `lending.collector_area_owner(...)` rule from Plan 1. Do not duplicate ownership precedence in Python.

For each effective Client path:

1. identify the explicit current `client.area_uid`;
2. walk ancestors with a recursive CTE;
3. include only ancestors + effective Client nodes that belong to this authenticated route;
4. return nodes in server route order using hierarchical sibling `sort_order`.

Keep `CollectorRouteRecord.areas` for compatibility. Add a separate typed `area_nodes` tuple rather than replacing legacy fields in one risky change.

- [ ] **Step 4: Prove child override fail-closed behavior**

Add a focused PostgreSQL proof using the disposable DB path:

- parent A at Calahan;
- child B at NIA;
- Client at NIA;
- A route query returns zero NIA Client rows;
- B route query returns the NIA Client;
- same-specificity ambiguity causes no route owner rather than duplicate route visibility.

- [ ] **Step 5: Run GREEN**

```bash
python -m pytest \
  gilbic_backend/tests/test_collector_route_repository.py \
  gilbic_backend/tests/test_collector_route_api.py -q
```

Then run the project disposable PostgreSQL validation covering 0098 + 0113 Area ownership.

- [ ] **Step 6: Commit**

```bash
git add \
  gilbic_backend/src/gilbic_backend/collector_route_repository.py \
  gilbic_backend/src/gilbic_backend/collector_route_api.py \
  gilbic_backend/tests/test_collector_route_repository.py \
  gilbic_backend/tests/test_collector_route_api.py
git commit -m "feat: expose Collector route Area hierarchy"
```

---

### Task 2: Parse and group arbitrary-depth Area trees in Flutter without breaking legacy routes

**Files:**
- Modify: `gilbic_mobile/lib/src/core/collector/collector_route.dart`
- Modify: `gilbic_mobile/lib/src/core/collector/collector_route_grouping.dart`
- Modify: `gilbic_mobile/test/collector_route_repository_test.dart`
- Modify: `gilbic_mobile/test/collector_route_grouping_test.dart`

**Interfaces:**
- Add `CollectorRouteAreaNode` model with the server fields from Task 1.
- `CollectorRoute` gains `areaNodes` while retaining `areas`.
- `CollectorRouteEntry` gains optional `areaUid` while retaining `area`.
- Add a hierarchical view model, e.g. `CollectorRouteTreeNode`, containing child nodes plus direct Client groups.
- Keep `groupCollectorRoute(...)` compatibility for existing screens such as master review until they are intentionally migrated.
- Add `buildCollectorRouteTree(route)` for the new hierarchy UI.

- [ ] **Step 1: Add RED parsing tests**

Extend `collector_route_repository_test.dart` with a payload containing:

```json
"area_nodes": [
  {"area_uid":"cardona","parent_area_uid":null,"name":"Cardona","full_path":"Cardona","depth":0,"sort_order":0},
  {"area_uid":"calahan","parent_area_uid":"cardona","name":"Calahan","full_path":"Cardona › Calahan","depth":1,"sort_order":0},
  {"area_uid":"balayong","parent_area_uid":"calahan","name":"Balayong","full_path":"Cardona › Calahan › Balayong","depth":2,"sort_order":0}
]
```

Prove all stable IDs and order parse, and an old payload with only `areas` still parses.

- [ ] **Step 2: Add RED hierarchy grouping tests**

In `collector_route_grouping_test.dart`, prove:

- arbitrary 7-level depth builds without special-casing level numbers;
- one Client explicitly at the deepest node appears once, not once per ancestor;
- ancestors show derived subtree Client counts;
- siblings preserve server order `Balayong, NIA, Main Calahan` even when alphabetical order differs;
- a missing/legacy `area_uid` falls back to one flat legacy group safely;
- multiple loans for one Client stay one Client row with Regular before 7x7 as today.

- [ ] **Step 3: Run RED**

```bash
cd gilbic_mobile
flutter test \
  test/collector_route_repository_test.dart \
  test/collector_route_grouping_test.dart
```

- [ ] **Step 4: Implement minimum models/tree builder**

Build lookup maps by `areaUid`/`parentAreaUid`. Preserve incoming node order. Never derive hierarchy by splitting `full_path`; stable IDs are authoritative when present.

Legacy fallback may use the existing flat grouping only when no stable node is available.

- [ ] **Step 5: Run GREEN**

```bash
cd gilbic_mobile
flutter test \
  test/collector_route_repository_test.dart \
  test/collector_route_grouping_test.dart
```

- [ ] **Step 6: Commit**

```bash
git add \
  gilbic_mobile/lib/src/core/collector/collector_route.dart \
  gilbic_mobile/lib/src/core/collector/collector_route_grouping.dart \
  gilbic_mobile/test/collector_route_repository_test.dart \
  gilbic_mobile/test/collector_route_grouping_test.dart
git commit -m "feat: model hierarchical Collector routes"
```

---

### Task 3: Replace the flat Area ledger stack with collapsible hierarchy navigation

**Files:**
- Modify: `gilbic_mobile/lib/src/features/collector/collector_route_page.dart`
- Modify: `gilbic_mobile/lib/src/features/collector/collector_client_ledger.dart`
- Create: `gilbic_mobile/lib/src/features/collector/collector_route_tree.dart`
- Modify: `gilbic_mobile/lib/src/features/collector/collector_route_header_cards.dart`
- Create: `gilbic_mobile/test/collector_route_hierarchy_test.dart`
- Keep existing payment tests Green, especially:
  - `gilbic_mobile/test/collector_combined_one_tap_test.dart`
  - `gilbic_mobile/test/collector_route_collection_gate_test.dart`
  - `gilbic_mobile/test/collector_route_receipt_visibility_test.dart`

**Approved UI:**

```text
Cardona
  Calahan
    Balayong
      Mabini St.
        Client rows...
    NIA
      Client rows...
```

Branches are expandable/collapsible. Client rows keep the current compact columns:

```text
CLIENT / STATUS | REG | 7x7 | TODAY
```

- [ ] **Step 1: Write RED widget tests**

Prove:

- top-level City renders first;
- tapping Calahan reveals its child nodes;
- tapping Balayong reveals deeper descendants/Clients;
- a deep Client is rendered exactly once;
- full address, ID, Meralco, business/residential label, and photo are absent from the normal route row;
- Regular + 7x7 one-tap Pay still appears on the Client row when exact-normal conditions hold;
- route refresh/payment does not forcibly expand every branch;
- an offline cached hierarchy displays but remains read-only for collection writes.

- [ ] **Step 2: Run RED**

```bash
cd gilbic_mobile
flutter test test/collector_route_hierarchy_test.dart
```

- [ ] **Step 3: Implement `CollectorRouteTree`**

Use local `Set<String> expandedAreaUids` state in `CollectorRoutePage`. Default to a minimal useful state: root route nodes may render, but deeper branches expand only when the Collector opens them. Do not render the whole tree expanded on every refresh.

Reuse `CollectorClientLedgerSection` for the Client table content, but separate the Area header/tree navigation from the ledger so unlimited depth does not create nested full-width cards inside full-width cards.

- [ ] **Step 4: Preserve current payment/correction behavior**

Do not rewrite `_payNow`, `_payCombined`, detailed-payment validation, offline gates, or correction rules unless required by widget wiring. Existing financial tests are the regression boundary.

- [ ] **Step 5: Run GREEN + regressions**

```bash
cd gilbic_mobile
flutter test \
  test/collector_route_hierarchy_test.dart \
  test/collector_combined_one_tap_test.dart \
  test/collector_route_collection_gate_test.dart \
  test/collector_route_receipt_visibility_test.dart \
  test/collector_route_grouping_test.dart
```

- [ ] **Step 6: Commit**

```bash
git add \
  gilbic_mobile/lib/src/features/collector/collector_route_page.dart \
  gilbic_mobile/lib/src/features/collector/collector_client_ledger.dart \
  gilbic_mobile/lib/src/features/collector/collector_route_tree.dart \
  gilbic_mobile/lib/src/features/collector/collector_route_header_cards.dart \
  gilbic_mobile/test/collector_route_hierarchy_test.dart
git commit -m "feat: add collapsible Collector route hierarchy"
```

---

### Task 4: Create a hidden Client Tools surface without duplicating financial logic

**Files:**
- Create: `gilbic_mobile/lib/src/features/collector/collector_client_tools_sheet.dart`
- Modify: `gilbic_mobile/lib/src/features/collector/collector_route_page.dart`
- Modify: `gilbic_mobile/lib/src/features/collector/collector_client_ledger.dart`
- Create: `gilbic_mobile/test/collector_client_tools_test.dart`

**Client Tools menu:**
- Payment details / other amount → existing `CollectionEntryPage`.
- Unable to Pay / Past Due → existing `CollectionEntryPage` mode/flow.
- Correction → existing allowed own-unremitted correction flow.
- Receipts/history → existing route receipt detail when available.
- Renewal → existing Collector renewal flow when eligible.
- Schedule → new read-only schedule page from Task 5.
- Collection location → new read-only location panel from Task 6.
- Notes/history: show currently authoritative operational notes already returned by route; do not invent a new write API in this plan unless a separate existing note endpoint is found during implementation.

- [ ] **Step 1: Write RED menu/widget tests**

Prove tapping a Client opens Client Tools rather than dumping full profile data into the normal route.

Prove:

- `Payment details` routes to existing financial flow;
- `Correction` appears only when current rules allow it;
- `Schedule` appears read-only;
- `Collection location` is on-demand;
- Staff/Management-only mutation controls do not exist;
- Client identity/address source evidence does not appear in the menu itself.

- [ ] **Step 2: Run RED**

```bash
cd gilbic_mobile
flutter test test/collector_client_tools_test.dart
```

- [ ] **Step 3: Implement a thin navigation sheet**

The sheet receives the existing grouped Client + loaded route state and callbacks. It must not implement payment allocation or permission decisions independently; delegate to existing page methods/repositories.

- [ ] **Step 4: Run GREEN + one-tap regressions**

```bash
cd gilbic_mobile
flutter test \
  test/collector_client_tools_test.dart \
  test/collector_combined_one_tap_test.dart \
  test/collector_route_collection_gate_test.dart
```

- [ ] **Step 5: Commit**

```bash
git add \
  gilbic_mobile/lib/src/features/collector/collector_client_tools_sheet.dart \
  gilbic_mobile/lib/src/features/collector/collector_route_page.dart \
  gilbic_mobile/lib/src/features/collector/collector_client_ledger.dart \
  gilbic_mobile/test/collector_client_tools_test.dart
git commit -m "feat: add Collector Client Tools"
```

---

### Task 5: Add the approved read-only row-by-row Client Schedule view

**Files:**
- Create: `gilbic_mobile/lib/src/core/collector/collector_schedule.dart`
- Create: `gilbic_mobile/lib/src/core/collector/collector_schedule_repository.dart`
- Modify: `gilbic_mobile/lib/src/core/config/api_config.dart`
- Create: `gilbic_mobile/lib/src/features/collector/collector_client_schedule_page.dart`
- Modify: `gilbic_mobile/lib/src/features/collector/collector_client_tools_sheet.dart`
- Create: `gilbic_mobile/test/collector_schedule_repository_test.dart`
- Create: `gilbic_mobile/test/collector_client_schedule_test.dart`

**Existing server authority:**
- `GET /api/mobile/v1/collector/loans/{loan_id}/schedule`
- permission `route.view`
- server verifies Collector ownership/access
- payload has `read_only: true`
- existing rows already expose date, status, current amount, paid/prepaid/remaining amounts, Past Due reason/note, promise fields, no-collection reason, and maturity summary.

- [ ] **Step 1: Write RED repository parsing tests**

Use actual server-like schedule JSON and prove parsing of:

- Paid row;
- Due row;
- Past Due row + reason;
- Advance/prepaid-covered row;
- future scheduled row;
- Regular and 7x7 `kind`/loan type;
- base vs updated maturity;
- extension slot count;
- `read_only=true`.

- [ ] **Step 2: Run RED**

```bash
cd gilbic_mobile
flutter test test/collector_schedule_repository_test.dart
```

- [ ] **Step 3: Implement repository/model**

Use the same authenticated device-header pattern as `SpinaCollectorRouteRepository`. Add:

```dart
static Uri collectorScheduleEndpoint(String loanId) => endpoint(
  '/api/mobile/v1/collector/loans/${Uri.encodeComponent(loanId)}/schedule',
);
```

No write method exists in this repository.

- [ ] **Step 4: Write RED schedule page tests**

For one Client with Regular + 7x7, open Schedule from Client Tools and show separate loan sections/tabs if both loans exist. Each section renders ordered rows with:

- date;
- amount;
- status;
- tap-for-detail affordance.

Row detail may show only data the server already supplies: paid amount, prepaid amount, remaining amount, Past Due reason/note, promise date/status, no-collection reason, principal/interest component when present.

Prove there is no Edit/Save/Change Maturity control.

- [ ] **Step 5: Implement the read-only page**

Do not merge Regular + 7x7 into a fake combined schedule. They remain authoritative loan schedules presented together under one Client Tools action.

- [ ] **Step 6: Run GREEN**

```bash
cd gilbic_mobile
flutter test \
  test/collector_schedule_repository_test.dart \
  test/collector_client_schedule_test.dart
```

- [ ] **Step 7: Commit**

```bash
git add \
  gilbic_mobile/lib/src/core/collector/collector_schedule.dart \
  gilbic_mobile/lib/src/core/collector/collector_schedule_repository.dart \
  gilbic_mobile/lib/src/core/config/api_config.dart \
  gilbic_mobile/lib/src/features/collector/collector_client_schedule_page.dart \
  gilbic_mobile/lib/src/features/collector/collector_client_tools_sheet.dart \
  gilbic_mobile/test/collector_schedule_repository_test.dart \
  gilbic_mobile/test/collector_client_schedule_test.dart
git commit -m "feat: add read-only Collector Client schedule"
```

---

### Task 6: Add route-scoped verified collection-location details, without inventing missing KYC data

**Files:**
- Create: `gilbic_backend/src/gilbic_backend/collector_client_detail_repository.py`
- Create: `gilbic_backend/src/gilbic_backend/collector_client_detail_api.py`
- Modify: `gilbic_backend/src/gilbic_backend/main.py`
- Create: `gilbic_backend/tests/test_collector_client_detail_api.py`
- Create: `gilbic_mobile/lib/src/core/collector/collector_client_detail.dart`
- Create: `gilbic_mobile/lib/src/core/collector/collector_client_detail_repository.dart`
- Modify: `gilbic_mobile/lib/src/core/config/api_config.dart`
- Create: `gilbic_mobile/lib/src/features/collector/collector_collection_location_page.dart`
- Modify: `gilbic_mobile/lib/src/features/collector/collector_client_tools_sheet.dart`
- Create: `gilbic_mobile/test/collector_collection_location_test.dart`

**Boundary:** Current repo search does not show an authoritative collection-location/photo data model. Therefore this task must be implemented defensively after inspecting the then-current onboarding/CIF schema.

The endpoint contract is fixed even if the underlying fields are initially nullable:

`GET /api/mobile/v1/collector/clients/{client_id}/collection-location`

Response:

```json
{
  "client_id": "...",
  "collection_location_status": "verified|not_verified",
  "display_address": null,
  "landmark": null,
  "photo_url": null,
  "verified_at": null
}
```

Rules:

- server requires active authenticated Collector + `route.view`;
- server proves the Client's current Area is effectively owned by this Collector **or** covered by valid delegated access;
- no route access → 404/403 without leaking whether the Client/location exists;
- return only approved collection-location data, never ID/Meralco raw evidence;
- if authoritative data does not exist, return `not_verified` with null detail fields;
- do not create a photo upload/write path in Priority #5;
- if Plan 1/ongoing CIF work later introduces the verified location table, adapt only the repository read query, not the API/mobile contract.

- [ ] **Step 1: Write RED backend authorization tests**

Prove owner Collector may read, overridden parent Collector may not read child Client, valid delegated Collector may read within scope, unrelated Collector cannot probe existence, and payload excludes KYC/source evidence.

- [ ] **Step 2: Run RED**

```bash
python -m pytest gilbic_backend/tests/test_collector_client_detail_api.py -q
```

- [ ] **Step 3: Implement minimum read endpoint**

Use `lending.collector_area_owner(client.area)` plus the existing delegated-access function. Prefer stable `client.area_uid` from Plan 1 when selecting route context, but keep full-path compatibility during migration.

If no verified collection-location backing record exists, return `not_verified`; do **not** copy `clients.area` into `display_address` because operational Area is not the physical collection address.

- [ ] **Step 4: Add RED Flutter location tests**

Prove Client Tools location page shows:

- verified address/landmark/photo when provided;
- `Collection location not yet verified` when status is not verified;
- no source-ID/Meralco address fields;
- no edit/upload button.

- [ ] **Step 5: Implement Flutter reader/page**

Use authenticated device headers. Render network images only from the server-provided URL and handle missing/broken image without blocking the rest of Client Tools.

- [ ] **Step 6: Run GREEN**

```bash
python -m pytest gilbic_backend/tests/test_collector_client_detail_api.py -q
cd gilbic_mobile
flutter test test/collector_collection_location_test.dart
```

- [ ] **Step 7: Commit**

```bash
git add \
  gilbic_backend/src/gilbic_backend/collector_client_detail_repository.py \
  gilbic_backend/src/gilbic_backend/collector_client_detail_api.py \
  gilbic_backend/src/gilbic_backend/main.py \
  gilbic_backend/tests/test_collector_client_detail_api.py \
  gilbic_mobile/lib/src/core/collector/collector_client_detail.dart \
  gilbic_mobile/lib/src/core/collector/collector_client_detail_repository.dart \
  gilbic_mobile/lib/src/core/config/api_config.dart \
  gilbic_mobile/lib/src/features/collector/collector_collection_location_page.dart \
  gilbic_mobile/lib/src/features/collector/collector_client_tools_sheet.dart \
  gilbic_mobile/test/collector_collection_location_test.dart
git commit -m "feat: show verified Collector collection location"
```

---

### Task 7: Preserve route hierarchy state through refresh/cache and complete mobile acceptance

**Files:**
- Modify only if needed:
  - `gilbic_mobile/lib/src/core/collector/collector_route_cache.dart`
  - `gilbic_mobile/lib/src/core/collector/collector_route_cache_sqlcipher.dart`
  - `gilbic_mobile/lib/src/core/collector/collector_route_loader.dart`
  - `gilbic_mobile/lib/src/features/collector/collector_route_page.dart`
- Create or modify focused tests under `gilbic_mobile/test/`.

- [ ] **Step 1: Add RED cache/state tests**

Prove:

- `area_nodes` survive route JSON cache round-trip;
- cache cannot manufacture a node/Client absent from server payload;
- offline cached route hierarchy renders but financial buttons remain disabled;
- after successful payment refresh, the last selected/expanded branch remains open when that branch still exists;
- if the branch no longer exists after server reassignment, state safely falls back to available route roots.

- [ ] **Step 2: Run RED**

Run the focused route cache + hierarchy tests.

- [ ] **Step 3: Implement minimum persistence/state reconciliation**

Prefer existing `CollectorRoute.toJson()` cache shape so `area_nodes` serialize naturally. Keep expanded UI state in memory only unless a current lightweight preference mechanism already exists; YAGNI forbids adding a new persistence store solely for expansion state.

- [ ] **Step 4: Full focused mobile regression**

```bash
cd gilbic_mobile
flutter test \
  test/collector_route_repository_test.dart \
  test/collector_route_grouping_test.dart \
  test/collector_route_hierarchy_test.dart \
  test/collector_client_tools_test.dart \
  test/collector_schedule_repository_test.dart \
  test/collector_client_schedule_test.dart \
  test/collector_collection_location_test.dart \
  test/collector_combined_one_tap_test.dart \
  test/collector_route_collection_gate_test.dart \
  test/collector_route_receipt_visibility_test.dart
flutter analyze
```

- [ ] **Step 5: Emulator acceptance**

Using disposable/test data only, verify:

1. Collector A sees `Cardona → Calahan → Balayong` but not child override `NIA → Collector B`.
2. Collector B sees NIA.
3. Manual sibling order matches Staff/Management Area Management order.
4. Deep route `Cardona → Calahan → Balayong → Mabini Street → Purok 2 → Riverside → Block A` is navigable without a fixed-depth failure.
5. Client row stays compact and one-tap Pay still works for an exact-normal Regular + 7x7 case.
6. Client Tools opens Payment details, Schedule, and Collection location without exposing full KYC evidence on the route.
7. Schedule rows are read-only and reflect current server operational rows.
8. Missing collection-location data displays `not yet verified` rather than a guessed address.
9. Offline copy is visibly read-only.

- [ ] **Step 6: Commit any final focused fixes**

Do not commit generated build artifacts.

---

### Task 8: Exact-head CI, documentation, and handoff

**Files:**
- Modify only as needed:
  - `docs/architecture/system-map.md`
  - existing Collector/Area feature documentation
  - CI validation scripts only if new focused tests are not already exercised by required lanes.

- [ ] **Step 1: Run all three Priority #5 plan acceptance suites**

Server:

```bash
python -m pytest \
  gilbic_backend/tests/test_area_management_migration.py \
  gilbic_backend/tests/test_area_management_repository.py \
  gilbic_backend/tests/test_area_management_api.py \
  gilbic_backend/tests/test_area_management_postgres.py \
  gilbic_backend/tests/test_collector_route_repository.py \
  gilbic_backend/tests/test_collector_route_api.py \
  gilbic_backend/tests/test_collector_client_detail_api.py -q
```

Portal:

```bash
cd spina_portal
node --test tests/area-management.test.mjs
npm run check:portal
```

Mobile:

```bash
cd gilbic_mobile
flutter test
flutter analyze
```

Use the repository's normal full backend/security/financial/disposable-PostgreSQL validation after focused checks pass.

- [ ] **Step 2: Verify exact-head CI once**

Required lanes must all be Green on the exact Priority #5 head before calling the implementation verified. Do not infer Green from an older commit.

- [ ] **Step 3: Create/update Draft PR and project state**

Keep it Draft/open/unmerged until explicit Management approval. Update:

- GitHub Master Issue #296;
- Notion `Spina Current Project State — Company Release Build`;
- Create State `SPINA Lending App`.

Record exact head SHA, CI run/jobs, completed Plan 1/2/3 scope, and explicit deferrals.

- [ ] **Step 4: Explicit deferrals remain**

Do not silently add:

- live collection-location photo enrollment/upload;
- live biometric/liveness/eGov integration;
- production migration/deployment;
- City Manager/Area Manager global roles;
- automatic route optimization/maps/GPS tracking;
- Collector permanent Area mutation;
- second mobile schedule engine.

## Definition of Done

Priority #5 is implementation-complete only when all of these are proved on the exact head:

1. Staff/Management can manage arbitrary-depth operational Areas through Plan 2 using Plan 1 server authority.
2. Parent Collector assignment + child override resolves exactly one effective permanent Collector and fails closed on ambiguity.
3. Collector phone renders only its effective ordered hierarchy and never the overridden child's Clients.
4. Manual route order reaches the Collector phone unchanged.
5. A Client explicitly assigned to a deep node appears once under derived ancestors.
6. Normal route rows remain compact: Client, REG, 7x7, Advance/Past Due/note, TODAY action.
7. Existing exact one-tap Regular + 7x7 atomic payment remains Green.
8. Hidden Client Tools expose approved operational details without cluttering the route.
9. Client Schedule is row-by-row, read-only, and powered by the existing authoritative server schedule.
10. Collection location is read-only, route-scoped, and never guessed from operational Area or source-backed ID/Meralco addresses.
11. Offline cached hierarchy is read-only and cannot widen authorization.
12. Historical collection/remittance/custody/accounting evidence remains immutable across Area changes.
13. No live/prod mutations or deployment occurred without separate explicit Management approval.
