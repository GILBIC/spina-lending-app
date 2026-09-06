# Area Management Server Authority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make PostgreSQL/FastAPI the single authoritative Area-management boundary for the approved City/Municipality → Barangay → unlimited Subarea tree, permanent Collector ownership, Client operational Area assignment, safe transfer timing, ordering, retirement, and audit.

**Architecture:** Add stable PostgreSQL Area nodes while retaining synchronized full-path text for current route/report compatibility. Keep the existing `lending.collector_area_owner(...)` most-specific-owner rule instead of replacing it. Staff/Employee and Management perform normal Area and Collector-assignment mutations through permission-gated FastAPI endpoints; Management alone retires/reactivates. Client transfers are immediate when no official collection exists that business date, otherwise persisted as a pending transfer for the next authoritative collection date and applied idempotently before route/collection ownership is evaluated.

**Tech Stack:** PostgreSQL 17/Supabase-compatible SQL, psycopg 3, FastAPI/Pydantic, pytest, existing `open_connection()`, existing `authenticated_device_context()`, existing `core.audit_logs`, existing hierarchical ownership functions from migration 0098.

**Spec:** `docs/superpowers/specs/2026-09-06-area-management-design.md`

## Scope decomposition

This is **Plan 1 of 3** for Priority #5.

- Plan 1 — this file: PostgreSQL/FastAPI Area authority, ownership, Client transfer timing, retirement, and route-reader compatibility.
- Plan 2 — `2026-09-07-area-management-portal.md`: Staff/Management Web/PC Area tree and actions.
- Plan 3 — `2026-09-07-area-management-collector-mobile.md`: Collector hierarchy navigation, compact route rows, hidden Client tools, schedule, and collection-location photo.

Do not pull Plan 2 or Plan 3 UI behavior into this implementation slice.

## Global Constraints

- Rebase the implementation branch onto the then-current `main` before starting. The approved onboarding Draft PR #420 reserves migration `0112`; this plan therefore uses `0113` for Area Management and must not rename/reuse `0112`.
- No production deployment, production DB migration, live Auth mutation, live Client data mutation, or merge without explicit Management approval.
- Use only disposable/test PostgreSQL data during development and hosted validation.
- PostgreSQL/FastAPI is authoritative for Web/Mobile Area mutations. Do not create a second writable Area tree in Flutter, Portal, or desktop code.
- Preserve existing full path text (`clients.area`, `collector_area_assignments.area`) during migration for compatibility, but stable Area IDs become the mutation authority.
- Do not guess hierarchy from legacy flat text. Every distinct legacy path becomes an unmapped root until Staff places it correctly.
- Normal managed hierarchy labels are root = City/Municipality, child of managed City = Barangay, every deeper level = Subarea. No fixed Subarea depth.
- Staff/Employee + Management may create/rename/move/reorder Areas and assign/reassign Collector/Client Areas through exact permissions.
- Management alone may retire/reactivate Areas.
- Collectors cannot change permanent ownership.
- Parent Collector assignment includes descendants; a more-specific child assignment overrides the inherited parent only for that branch.
- At any candidate Client Area path, exactly one effective permanent Collector may resolve. Equal-specificity ambiguity fails closed.
- Temporary delegated access remains separate from permanent ownership and must continue to fail closed when ownership changes.
- Client has one explicit current operational Area node. Ancestor membership is derived, never duplicated as multiple Client assignment rows.
- Residence, ID, Meralco, and business address fields are not automatic route assignments.
- A Client transfer that has no official collection that business date is immediate. If already collected, defer to the next persisted authoritative collection date; never invent a date.
- Historical collection/receipt/remittance/custody/accounting/audit evidence is immutable and must never be rewritten by Area moves or Client transfers.
- Strict TDD: write the failing focused test first, observe the expected failure, then implement the minimum Green behavior.
- Keep commits small and task-scoped. Do not mix unrelated cleanup.

---

### Task 1: Add authoritative Area schema, permissions, and safe legacy backfill

**Files:**
- Create: `gilbic_backend/sql/0113_add_authoritative_area_management.sql`
- Create: `gilbic_backend/tests/test_area_management_migration.py`
- Modify: `tools/run_schema_upgrade_validation.py` only if the current migration runner has an explicit last-migration allowlist that must include 0113

**Interfaces:**
- Produces `lending.area_nodes` with stable UUID identity and parent/child hierarchy.
- Adds nullable `area_uid` links to `lending.clients` and `lending.collector_area_assignments` while retaining existing text paths.
- Produces `lending.client_area_pending_transfers` and immutable `lending.client_area_transfer_history`.
- Produces permissions:
  - `area.manage` → Employee + Management
  - `area.collector.assign` → Employee + Management
  - `area.client.assign` → Employee + Management
  - `area.retire` → Management only
- Backfills each distinct legacy nonblank Client/Collector path as one `is_legacy_unmapped=true` root without parsing separators.

- [ ] **Step 1: Write the migration contract test**

Create `gilbic_backend/tests/test_area_management_migration.py` and assert at minimum:

```python
from pathlib import Path

SQL = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0113_add_authoritative_area_management.sql"
).read_text(encoding="utf-8").lower()


def test_area_management_schema_contract() -> None:
    assert "create table if not exists lending.area_nodes" in SQL
    assert "parent_area_uid uuid" in SQL
    assert "full_path text not null" in SQL
    assert "sort_order integer not null" in SQL
    assert "is_active boolean not null" in SQL
    assert "is_legacy_unmapped boolean not null" in SQL
    assert "add column if not exists area_uid uuid" in SQL
    assert "client_area_pending_transfers" in SQL
    assert "client_area_transfer_history" in SQL
    assert "area.manage" in SQL
    assert "area.collector.assign" in SQL
    assert "area.client.assign" in SQL
    assert "area.retire" in SQL
    assert "('employee', 'area.retire')" not in SQL
    assert "('management', 'area.retire')" in SQL
    assert "update lending.collection_transactions" not in SQL
    assert "delete from lending.collection_transactions" not in SQL
```

Also assert there is no fixed depth check such as `depth <= 4` or named `subarea_1` columns.

- [ ] **Step 2: Run RED**

```bash
python -m pytest gilbic_backend/tests/test_area_management_migration.py -q
```

Expected: FAIL because `0113_add_authoritative_area_management.sql` does not exist.

- [ ] **Step 3: Implement the minimum 0113 schema**

Use this shape; keep naming consistent with existing snake_case SQL:

```sql
create table if not exists lending.area_nodes (
    area_uid uuid primary key default gen_random_uuid(),
    parent_area_uid uuid references lending.area_nodes(area_uid) on delete restrict,
    name text not null,
    full_path text not null,
    depth integer not null default 0 check (depth >= 0),
    sort_order integer not null default 0 check (sort_order >= 0),
    is_active boolean not null default true,
    is_legacy_unmapped boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (btrim(name) <> ''),
    check (btrim(full_path) <> '')
);

create unique index if not exists lending_area_nodes_full_path_lower_uidx
    on lending.area_nodes(lower(lending.normalize_area_path(full_path)));
create index if not exists lending_area_nodes_parent_order_idx
    on lending.area_nodes(parent_area_uid, sort_order, lower(name));

alter table lending.clients
    add column if not exists area_uid uuid
        references lending.area_nodes(area_uid) on delete restrict;

alter table lending.collector_area_assignments
    add column if not exists area_uid uuid
        references lending.area_nodes(area_uid) on delete restrict;
```

Backfill rules:

1. Read distinct normalized nonblank `lending.clients.area` and `lending.collector_area_assignments.area`.
2. Insert each **entire existing path string as one root node** with `parent_area_uid=NULL`, `depth=0`, `is_legacy_unmapped=true`.
3. Never split on `›`, `/`, `-`, comma, or address text during backfill.
4. Link Client/assignment `area_uid` by case-insensitive normalized full-path equality.
5. Abort migration if the same exact active Area path is already permanently assigned to different Collectors; do not pick a winner. This protects creation of a partial unique active-node ownership index.

After the preflight conflict guard, add:

```sql
create unique index if not exists lending_collector_active_area_uid_uidx
    on lending.collector_area_assignments(area_uid)
    where is_active = true and area_uid is not null;
```

The pending-transfer table must have one pending row per Client and store current/target node IDs, target path snapshot, effective date, scheduling actor/time, and `applied_at`/`cancelled_at` state. The history table must append every immediate or applied deferred transfer with old/new node/path snapshot, effective date, scheduling actor, and application timestamp.

- [ ] **Step 4: Seed exact permissions**

Follow the existing 0111 role-permission style:

```sql
insert into core.permissions(code, description)
values
    ('area.manage', 'Create, rename, move, and reorder active Areas'),
    ('area.collector.assign', 'Assign permanent Areas to Collectors'),
    ('area.client.assign', 'Assign a Client current operational Area'),
    ('area.retire', 'Retire or reactivate an Area')
on conflict (code) do update set description = excluded.description;
```

Grant the first three to `employee` and `management`; grant `area.retire` only to `management`.

- [ ] **Step 5: Run migration contract GREEN**

```bash
python -m pytest gilbic_backend/tests/test_area_management_migration.py -q
```

Expected: PASS.

- [ ] **Step 6: Run disposable PostgreSQL migration proof**

Use the existing project migration/disposable PostgreSQL validation path. On a fresh DB, replay through 0113 and prove:

- legacy `CARDONA › CALAHAN` remains exactly one unmapped root, not two or three guessed nodes;
- Client and Collector assignment rows receive the same stable Area UID for the same normalized path;
- no collection/remittance/accounting history table is rewritten;
- conflicting exact permanent owners fail migration rather than silently dedupe.

Run the project’s hosted/disposable PostgreSQL validator plus:

```bash
python -m pytest gilbic_backend/tests/test_area_management_migration.py gilbic_backend/tests/test_delegated_area_access_postgres.py -q
```

Expected: all focused tests pass when `GILBIC_TEST_DATABASE_URL` is configured; PostgreSQL tests skip locally when it is not.

- [ ] **Step 7: Commit**

```bash
git add gilbic_backend/sql/0113_add_authoritative_area_management.sql gilbic_backend/tests/test_area_management_migration.py tools/run_schema_upgrade_validation.py
git commit -m "feat: add authoritative Area hierarchy schema"
```

Only include `tools/run_schema_upgrade_validation.py` if it actually required a 0113 allowlist update; otherwise leave it untouched.

---

### Task 2: Implement the read-only Area tree and effective ownership repository

**Files:**
- Create: `gilbic_backend/src/gilbic_backend/area_management_repository.py`
- Create: `gilbic_backend/tests/test_area_management_repository.py`

**Interfaces:**
- `PostgresAreaManagementRepository.list_tree()` → flat ordered node records sufficient for clients to build a tree.
- `list_collectors()` → active Collector account choices only.
- `search_clients(query, limit)` → Client identity + current explicit Area + effective Collector, no KYC evidence.
- `effective_collector(area_path)` continues to rely on `lending.collector_area_owner(...)`.
- Node payload fields: `area_uid`, `parent_area_uid`, `name`, `full_path`, `depth`, `sort_order`, `is_active`, `is_legacy_unmapped`, `explicit_collector`, `effective_collector`, `effective_collector_source_area_uid`, `direct_client_count`, `subtree_client_count`, `child_count`.

- [ ] **Step 1: Write RED repository tests with fake connection/cursors**

Cover:

- stable ordered node output;
- legacy roots remain identifiable;
- explicit Collector assignment differs from inherited effective Collector;
- Client search does not return ID/Meralco/onboarding evidence;
- subtree counts use hierarchy, not string-prefix guessing alone;
- inactive nodes are included only when requested.

- [ ] **Step 2: Run RED**

```bash
python -m pytest gilbic_backend/tests/test_area_management_repository.py -q
```

Expected: import/module failure.

- [ ] **Step 3: Implement focused dataclasses and reader methods**

Keep this module narrow. Do not put FastAPI request validation in the repository.

For effective Collector resolution, query the existing function rather than duplicating the precedence algorithm in Python:

```sql
select
    lending.collector_area_owner(node.full_path) as effective_collector_user_id
from lending.area_nodes node
where node.area_uid = %s
```

For inherited-source display, choose the most-specific active `collector_area_assignments` ancestor and return its `area_uid`; if two rows somehow survive at the same specificity, expose no effective owner and let the API report the fail-closed state.

- [ ] **Step 4: Run GREEN**

```bash
python -m pytest gilbic_backend/tests/test_area_management_repository.py -q
```

- [ ] **Step 5: Commit**

```bash
git add gilbic_backend/src/gilbic_backend/area_management_repository.py gilbic_backend/tests/test_area_management_repository.py
git commit -m "feat: add Area Management read model"
```

---

### Task 3: Add audited create, rename, move, and reorder mutations

**Files:**
- Modify: `gilbic_backend/src/gilbic_backend/area_management_repository.py`
- Modify: `gilbic_backend/tests/test_area_management_repository.py`
- Create: `gilbic_backend/tests/test_area_management_postgres.py`

**Interfaces:**
- `create_area(actor_user_id, parent_area_uid, name)`
- `rename_area(actor_user_id, area_uid, name)`
- `preview_move(area_uid, new_parent_area_uid)`
- `move_area(actor_user_id, area_uid, new_parent_area_uid)`
- `reorder_siblings(actor_user_id, parent_area_uid, ordered_area_uids)`
- Every mutation writes one `core.audit_logs` event in the same transaction.
- Moving/renaming rewrites current compatibility paths only (`area_nodes.full_path`, current `clients.area`, current `collector_area_assignments.area`, pending target path snapshots when still pending). It never rewrites collection/remittance/accounting history.

- [ ] **Step 1: Add RED tests for structural safety**

Test all of these:

- root managed creation is allowed only with `parent_area_uid=None` and becomes `depth=0`, `is_legacy_unmapped=false`;
- child path is canonical `Parent › Child`;
- blank names and names containing the hierarchy separator are rejected;
- rename cascades descendant `full_path` and current compatibility text;
- move cascades whole subtree and recalculates depth;
- cannot move a node under itself or a descendant;
- cannot move under an inactive parent;
- case-insensitive duplicate target path is rejected;
- reordering accepts the complete sibling set exactly once and stores dense `0..n-1` order;
- audit details include old/new path or order without sensitive Client evidence;
- no SQL touches `lending.collection_transactions` or remittance/accounting evidence.

- [ ] **Step 2: Run RED**

```bash
python -m pytest gilbic_backend/tests/test_area_management_repository.py -q
```

Expected: new mutation tests fail because methods do not exist.

- [ ] **Step 3: Implement one transaction per mutation**

Use `SELECT ... FOR UPDATE` on the target subtree/siblings before planning the change. Build the full subtree with a recursive CTE so arbitrary depth works:

```sql
with recursive subtree as (
    select area_uid, parent_area_uid, name, full_path, depth
    from lending.area_nodes
    where area_uid = %s
    union all
    select child.area_uid, child.parent_area_uid, child.name,
           child.full_path, child.depth
    from lending.area_nodes child
    join subtree parent on child.parent_area_uid = parent.area_uid
)
select * from subtree
for update;
```

Do not add a hard maximum depth.

When a legacy unmapped root is placed beneath a managed node, clear `is_legacy_unmapped` for the moved root. Its descendants keep their own flag only if they are independently unmapped roots (normally none after subtree membership).

- [ ] **Step 4: Add PostgreSQL subtree proof**

In `test_area_management_postgres.py`, create at least 7 nested levels and prove create → rename → move → reorder works without a fixed-depth assumption:

`Cardona → Calahan → Balayong → Mabini St. → Purok 2 → Riverside → Block A`

Also insert an immutable collection transaction before the move and prove its stored `assignment_area` remains unchanged afterward.

- [ ] **Step 5: Run GREEN**

```bash
python -m pytest gilbic_backend/tests/test_area_management_repository.py gilbic_backend/tests/test_area_management_postgres.py -q
```

Expected: unit tests pass; PostgreSQL proof passes with test DB or skips when unavailable.

- [ ] **Step 6: Commit**

```bash
git add gilbic_backend/src/gilbic_backend/area_management_repository.py gilbic_backend/tests/test_area_management_repository.py gilbic_backend/tests/test_area_management_postgres.py
git commit -m "feat: add audited Area tree mutations"
```

---

### Task 4: Add permanent Collector assignment with inheritance and child override

**Files:**
- Modify: `gilbic_backend/src/gilbic_backend/area_management_repository.py`
- Modify: `gilbic_backend/tests/test_area_management_repository.py`
- Modify: `gilbic_backend/tests/test_area_management_postgres.py`
- Modify: `gilbic_backend/tests/test_delegated_area_access_postgres.py`

**Interfaces:**
- `assign_collector(actor_user_id, area_uid, collector_user_id)` sets the one explicit permanent owner for that exact node.
- `remove_collector_assignment(actor_user_id, area_uid)` removes only the exact-node override; inherited parent ownership becomes effective automatically.
- Parent and child assignments coexist.
- Only active accounts with the Collector role may be assigned.

- [ ] **Step 1: Add RED ownership tests**

Prove:

```text
Calahan -> Collector A
  Balayong -> inherited A
  NIA -> Collector B
```

Then remove NIA’s exact assignment and prove NIA resolves back to A.

Also prove:

- assigning B to NIA does not delete A’s Calahan assignment;
- the parent route owner no longer owns NIA while the override is active;
- an exact-node reassignment from B → C is atomic: prior exact assignment becomes inactive and C becomes active;
- a non-Collector or inactive Collector target is rejected;
- delegated grant from A for NIA becomes unusable after B overrides NIA, preserving existing 0098 behavior;
- no historical collection row is rewritten.

- [ ] **Step 2: Run RED**

```bash
python -m pytest gilbic_backend/tests/test_area_management_repository.py gilbic_backend/tests/test_delegated_area_access_postgres.py -q
```

- [ ] **Step 3: Implement assignment transaction**

Lock the Area node and active exact-node assignment rows. Deactivate the existing exact assignment when changing owner, then insert/reactivate the requested Collector assignment with both `area_uid` and the node’s canonical `full_path` text.

Do **not** create descendant assignment rows. Inheritance stays dynamic through `lending.collector_area_owner(...)`.

- [ ] **Step 4: Run GREEN**

```bash
python -m pytest gilbic_backend/tests/test_area_management_repository.py gilbic_backend/tests/test_area_management_postgres.py gilbic_backend/tests/test_delegated_area_access_postgres.py -q
```

- [ ] **Step 5: Commit**

```bash
git add gilbic_backend/src/gilbic_backend/area_management_repository.py gilbic_backend/tests/test_area_management_repository.py gilbic_backend/tests/test_area_management_postgres.py gilbic_backend/tests/test_delegated_area_access_postgres.py
git commit -m "feat: add inherited Collector Area ownership"
```

---

### Task 5: Implement one-current-Area Client assignment and automatic transfer timing

**Files:**
- Modify: `gilbic_backend/src/gilbic_backend/area_management_repository.py`
- Modify: `gilbic_backend/tests/test_area_management_repository.py`
- Modify: `gilbic_backend/tests/test_area_management_postgres.py`
- Modify: `gilbic_backend/src/gilbic_backend/collector_route_repository.py`
- Modify: `gilbic_backend/src/gilbic_backend/collector_schedule_repository.py`
- Modify: `gilbic_backend/src/gilbic_backend/other_area_repository.py`
- Modify: `gilbic_backend/src/gilbic_backend/collection_posting.py`
- Modify: `gilbic_backend/tests/test_collector_route_repository.py`
- Modify: `gilbic_backend/tests/test_collection_posting.py`

**Interfaces:**
- `preview_client_transfer(client_id, target_area_uid, as_of_date)` returns old/new Area, old/new effective Collector, `effective_date`, and `timing` (`immediate` or `next_collection_day`).
- `schedule_client_transfer(actor_user_id, client_id, target_area_uid, as_of_date)` performs immediate transfer or stores one pending transfer.
- `apply_due_client_area_transfers(connection, as_of_date, client_id=None)` idempotently activates due pending transfers before route/collection ownership reads.
- Current Client row retains only one explicit `area_uid` + compatibility `area` path.

- [ ] **Step 1: Add RED transfer-decision tests**

Cover:

1. No official nonvoided collection on 2026-09-07 → immediate transfer effective 2026-09-07.
2. Official collection already exists on 2026-09-07 → choose the first future **persisted effective installment date** from the Client’s active authoritative contract schedule.
3. Skip persisted `No Collection` dates and dates where there is no active collection installment.
4. If already collected today and there is no future authoritative installment, fail with `client_transfer_next_collection_day_unavailable`; do not guess tomorrow.
5. A second pending request for the same Client replaces/cancels the prior pending request atomically and is audited.
6. Immediate transfer updates `clients.area_uid` + `clients.area` and appends history in the same transaction.
7. Deferred transfer does not change today’s current Client Area.
8. Applying a due transfer is idempotent and writes exactly one history row.
9. Historical collection `assignment_area`, assigned Collector, recorder, receipt, remittance, and audit evidence remains unchanged.

- [ ] **Step 2: Run RED**

```bash
python -m pytest gilbic_backend/tests/test_area_management_repository.py gilbic_backend/tests/test_area_management_postgres.py -q
```

- [ ] **Step 3: Implement effective-date calculation from authoritative schedule**

Use the persisted operational schedule tables already used by `collector_schedule_repository.py`; do not recalculate the loan calendar independently.

The future date query should be based on `lending.loan_contract_installments_operational.effective_due_date` for active loans and active/verified schedules. Pick the minimum date strictly after `as_of_date` that still has an operational installment.

If a Client has both Regular and 7x7, the next collection day is the minimum valid future effective due date across the Client’s active loans. This keeps the Client route transfer date aligned to the earliest real field-collection obligation.

- [ ] **Step 4: Implement idempotent pending-transfer activation**

Inside `apply_due_client_area_transfers(...)`:

- lock due pending rows with `FOR UPDATE`;
- lock the Client row;
- verify target Area remains active;
- update exactly one current Client `area_uid/area`;
- mark pending row `applied_at`;
- append transfer history;
- leave immutable collection history untouched.

If the target Area became inactive before activation, fail closed and leave the Client on the old route; surface an operational conflict for Staff/Management resolution.

- [ ] **Step 5: Integrate due-transfer activation at authoritative ownership boundaries**

Call the helper before ownership is evaluated in:

- Collector route load for the route business date;
- Collector schedule lookup for the current Manila business date;
- Other-Area search/work list before deciding owner;
- `PostgresCollectionPostingBridge.post_collection()` **inside the same existing transaction** and before route ownership validation.

Do not add a second background scheduler. This lazy, idempotent activation is sufficient because every field action already passes through these server boundaries.

- [ ] **Step 6: Update route/posting regression tests**

In `test_collector_route_repository.py`, prove a due transfer is applied before route rows are read.

In `test_collection_posting.py`, adapt the fake cursor so the activation helper can run and prove a stale old-route Collector is rejected after the due transfer while the new effective owner can post.

Keep all existing one-tap, correction, custody, and accounting semantics unchanged.

- [ ] **Step 7: Run GREEN**

```bash
python -m pytest \
  gilbic_backend/tests/test_area_management_repository.py \
  gilbic_backend/tests/test_area_management_postgres.py \
  gilbic_backend/tests/test_collector_route_repository.py \
  gilbic_backend/tests/test_collection_posting.py \
  gilbic_backend/tests/test_collector_schedule_api.py -q
```

- [ ] **Step 8: Commit**

```bash
git add gilbic_backend/src/gilbic_backend/area_management_repository.py gilbic_backend/src/gilbic_backend/collector_route_repository.py gilbic_backend/src/gilbic_backend/collector_schedule_repository.py gilbic_backend/src/gilbic_backend/other_area_repository.py gilbic_backend/src/gilbic_backend/collection_posting.py gilbic_backend/tests/test_area_management_repository.py gilbic_backend/tests/test_area_management_postgres.py gilbic_backend/tests/test_collector_route_repository.py gilbic_backend/tests/test_collection_posting.py
git commit -m "feat: add automatic Client Area transfer timing"
```

---

### Task 6: Add Management-only retirement/reactivation safety

**Files:**
- Modify: `gilbic_backend/src/gilbic_backend/area_management_repository.py`
- Modify: `gilbic_backend/tests/test_area_management_repository.py`
- Modify: `gilbic_backend/tests/test_area_management_postgres.py`

**Interfaces:**
- `preview_retirement(area_uid)` reports active direct/subtree Clients, active explicit Collector assignments, active pending transfers targeting the subtree, and descendant count.
- `retire_area(actor_user_id, area_uid)` succeeds only when the full subtree is operationally clear.
- `reactivate_area(actor_user_id, area_uid)` reactivates the node only when its parent is active (or it is a root).
- Repository does not decide role; API permission `area.retire` is the Management-only gate.

- [ ] **Step 1: Add RED retirement tests**

Prove retirement rejects when any of these remain in the node/subtree:

- active Client current Area;
- active explicit Collector assignment;
- pending Client transfer target;
- active child that would remain operationally stranded.

Prove a clear used Area becomes inactive without deletion and remains queryable with `include_inactive=true`.

Prove reactivation does not rewrite historical rows and fails when parent remains inactive.

- [ ] **Step 2: Run RED**

```bash
python -m pytest gilbic_backend/tests/test_area_management_repository.py gilbic_backend/tests/test_area_management_postgres.py -q
```

- [ ] **Step 3: Implement minimal retire/reactivate mutations**

Use one transaction, row locks, dependency checks, and `core.audit_logs` action names:

- `area.retired`
- `area.reactivated`

Never `DELETE FROM lending.area_nodes` for a used node.

- [ ] **Step 4: Run GREEN**

```bash
python -m pytest gilbic_backend/tests/test_area_management_repository.py gilbic_backend/tests/test_area_management_postgres.py -q
```

- [ ] **Step 5: Commit**

```bash
git add gilbic_backend/src/gilbic_backend/area_management_repository.py gilbic_backend/tests/test_area_management_repository.py gilbic_backend/tests/test_area_management_postgres.py
git commit -m "feat: add safe Area retirement lifecycle"
```

---

### Task 7: Expose the protected Area Management API

**Files:**
- Create: `gilbic_backend/src/gilbic_backend/area_management_api.py`
- Create: `gilbic_backend/tests/test_area_management_api.py`
- Modify: `gilbic_backend/src/gilbic_backend/main.py`

**Interfaces:**

Read endpoints:
- `GET /api/v1/areas`
- `GET /api/v1/areas/collectors`
- `GET /api/v1/areas/clients?q=<query>`
- `GET /api/v1/areas/{area_id}/move-preview?new_parent_area_id=<uuid>`
- `GET /api/v1/areas/{area_id}/retirement-preview`
- `GET /api/v1/clients/{client_id}/area-transfer-preview?target_area_id=<uuid>`

Write endpoints:
- `POST /api/v1/areas`
- `PATCH /api/v1/areas/{area_id}`
- `POST /api/v1/areas/{area_id}/move`
- `POST /api/v1/areas/reorder`
- `PUT /api/v1/areas/{area_id}/collector`
- `DELETE /api/v1/areas/{area_id}/collector`
- `POST /api/v1/clients/{client_id}/area-transfer`
- `POST /api/v1/areas/{area_id}/retire`
- `POST /api/v1/areas/{area_id}/reactivate`

Permission mapping:
- tree/read + create/rename/move/reorder: `area.manage`
- Collector assignment/remove: `area.collector.assign`
- Client transfer preview/submit: `area.client.assign`
- retire/reactivate: `area.retire`

All endpoints require authenticated active-device context. Employee/Management role is enforced in addition to exact permission. `area.retire` naturally limits retirement/reactivation to Management because only Management receives it in 0113.

- [ ] **Step 1: Write RED API authorization and strict-body tests**

Follow existing `management_api.py` dependency-override style. Prove:

- missing `X-Device-Id` fails;
- revoked/unregistered device fails;
- Collector and Client roles fail even if a fake permission is injected;
- Employee with `area.manage` can create/rename/move/reorder but cannot retire;
- Employee with `area.collector.assign` can assign Collector;
- Management with `area.retire` can retire/reactivate;
- request models use `extra="forbid"`;
- API returns repository conflict codes as 409 without leaking SQL details.

- [ ] **Step 2: Run RED**

```bash
python -m pytest gilbic_backend/tests/test_area_management_api.py -q
```

Expected: import/module failure.

- [ ] **Step 3: Implement `area_management_api.py`**

Use one shared dependency:

```python
def area_staff_context(
    request: Request,
    authorization: str | None = Header(default=None),
    device_id: str | None = Header(default=None, alias="X-Device-Id"),
    auth_client = Depends(auth_client_dependency),
    accounts = Depends(account_repository_dependency),
) -> AccountContext:
    context = authenticated_device_context(...)
    if not ({"employee", "management"} & set(context.roles)):
        raise HTTPException(status_code=403, detail={"code": "area_staff_role_required"})
    return context
```

Then check the exact permission inside each endpoint. Keep response envelopes consistent with existing `/api/v1` endpoints.

- [ ] **Step 4: Mount router once in `main.py`**

Import `create_area_management_router` and include it once near other operational routers.

- [ ] **Step 5: Run GREEN**

```bash
python -m pytest gilbic_backend/tests/test_area_management_api.py -q
```

- [ ] **Step 6: Commit**

```bash
git add gilbic_backend/src/gilbic_backend/area_management_api.py gilbic_backend/src/gilbic_backend/main.py gilbic_backend/tests/test_area_management_api.py
git commit -m "feat: expose protected Area Management API"
```

---

### Task 8: Run full regression and disposable PostgreSQL acceptance proof

**Files:**
- Modify only if needed for verification wiring: existing disposable PostgreSQL validation scripts under `tools/`
- No product behavior changes in this task unless a test exposes a real bug; use a new RED/GREEN commit for any such fix.

**Acceptance proof:**

- [ ] **Step 1: Run focused backend suite**

```bash
python -m pytest -q \
  gilbic_backend/tests/test_area_management_migration.py \
  gilbic_backend/tests/test_area_management_repository.py \
  gilbic_backend/tests/test_area_management_api.py \
  gilbic_backend/tests/test_area_management_postgres.py \
  gilbic_backend/tests/test_delegated_area_access_postgres.py \
  gilbic_backend/tests/test_collector_route_repository.py \
  gilbic_backend/tests/test_collector_schedule_api.py \
  gilbic_backend/tests/test_collection_posting.py
```

Expected: all non-PostgreSQL tests pass; DB-gated tests pass when configured or skip locally.

- [ ] **Step 2: Run complete backend tests**

```bash
python -m pytest gilbic_backend/tests -q
```

Expected: no unexpected regression.

- [ ] **Step 3: Run hosted/disposable PostgreSQL validation**

Prove on a fresh disposable database through 0113:

1. seven-level hierarchy works;
2. manual sibling order persists;
3. parent Collector A owns descendants;
4. child Collector B overrides one branch;
5. removing B restores inherited A;
6. equal-specificity ambiguity fails closed;
7. Client deep-node membership is one explicit row + derived ancestors;
8. immediate transfer when no collection today;
9. deferred transfer to next authoritative collection date after same-day collection;
10. due transfer is applied before route/post ownership;
11. used Area retirement never deletes history;
12. delegated grant becomes stale when permanent ownership changes;
13. collection/remittance/custody/accounting historical evidence remains byte-for-byte/field-for-field unchanged where applicable.

- [ ] **Step 4: Run repository quality/security checks used by SPINA CI**

Run the same lint/type/security commands invoked by the current CI configuration; do not invent a lighter local substitute.

- [ ] **Step 5: Commit verification-only wiring if required**

If no validation script changed, do not create an empty commit. If wiring changed:

```bash
git add tools
 git commit -m "test: prove Area Management on disposable PostgreSQL"
```

- [ ] **Step 6: Push and wait for exact-head CI**

After pushing the implementation branch, report the exact head SHA and wait for the user’s **Red** / **Green** shorthand. Inspect exact-head CI once when reported. Do not continuously poll.

## Completion boundary

Plan 1 is complete only when exact-head CI proves the Area server authority and no unexpected regression. It does **not** implement the Portal tree or Flutter Collector hierarchy. Keep those for Plan 2 and Plan 3.
