# SPINA Priority #5 — Area Management Design

**Status:** Approved in design conversation on 2026-09-06; implementation has not started.

## Purpose

Area Management exists to make SPINA's collection geography easy to organize and to assign the correct operational route to each Collector without duplicate permanent ownership.

The design must stay simple for Staff/Management, work with Philippine-style locations, support very deep local subdivisions when needed, and reuse SPINA's existing hierarchical ownership and Collector-route rules instead of introducing a second routing system.

## Goals

1. Maintain one authoritative operational Area tree.
2. Allow Staff/Employee and Management to assign/reassign Areas to Collectors.
3. Support parent assignment inheritance with more-specific child overrides.
4. Resolve every active Client/location to exactly one effective permanent Collector at a time.
5. Allow unlimited practical nesting below Barangay, with no fixed `Subarea 1`, `Subarea 2`, etc. fields.
6. Let Staff/Management manually arrange Area order so Collector routes follow the actual field route rather than alphabetical order.
7. Keep Collector mobile routes compact and hierarchy-first.
8. Preserve historical collection, receipt, remittance, custody, recorder, and audit evidence when current Area assignments change.
9. Keep residential/business/source addresses separate from SPINA's operational collection hierarchy.

## Non-goals

- No separate City Manager or Area Manager global account roles for Priority #5.
- No second geography/routing engine.
- No automatic route assignment from a Client's residential address.
- No hard deletion of an Area that has already been used operationally.
- No Collector ability to directly edit schedule rows or permanent Area ownership.
- No rewrite of historical transactions when a Client or Area is moved.

## Existing foundations to reuse

SPINA already has important pieces that should remain authoritative or be aligned into the server implementation:

- `spina_app/area_hierarchy.py` provides stable Area node IDs, parent/child nesting, `depth`, `sort_order`, `is_active`, full display paths, and unlimited nesting.
- `spina_app/area_hierarchy_ops.py` already supports subtree rename/move/reorder behavior and cascades full paths through descendants and Client compatibility fields.
- `lending.collector_area_assignments` is the existing permanent Collector assignment source.
- Migration `0098_harden_hierarchical_collector_area_ownership.sql` already implements the approved ownership rule: parent assignments cover descendants, the most-specific assignment wins, and ambiguous same-specificity ownership fails closed.
- Existing delegated Collector access remains separate from permanent ownership.
- Existing cross-Collector payment, recorder, custody, remittance, and immutable-history controls remain authoritative.
- Priority #1's authoritative current operational schedule remains the only schedule engine.

Priority #5 must align these foundations around one server-authoritative operational Area model rather than creating parallel trees.

## 1. Geography and address separation

### Official/source-backed Client address

A Client's identity/address evidence is not the same thing as the Collector route.

SPINA may retain source-backed address information such as:

- address from accepted government ID;
- address from Meralco/service evidence;
- verified residential address;
- business/work address.

If ID and Meralco differ, both source values remain preserved. The verified current residence is established through the approved verification process rather than silently overwriting one source with the other.

### Collection location

A Client may normally pay at a house, business, or another approved collection point. The required location picture belongs to the verified collection location used in field operations.

Changing the normal collection point does not rewrite the Client's ID/Meralco/residential evidence.

### Operational Area hierarchy

The Collector route uses SPINA's operational hierarchy, not the raw residential address.

The normal hierarchy begins as:

`City/Municipality -> Barangay -> Subarea -> Subarea -> Subarea -> ...`

Example:

`Cardona -> Calahan -> Balayong -> Mabini Street -> Purok 2 -> Riverside -> Block A`

For newly managed hierarchy:

- root node = City/Municipality;
- direct child of the City/Municipality = Barangay;
- every level below Barangay = generic operational Subarea.

After Barangay, there is no fixed depth and no numbered Subarea columns. Any node may receive another child node when operations need a finer route section.

Typical child names may represent a sitio, purok, street, subdivision, compound, market cluster, local zone, or another practical collection section. SPINA does not need to falsely claim that every operational node is an official LGU level.

Legacy flat Areas may remain temporarily as unmapped roots during migration. SPINA must not guess their hierarchy; Staff can place them correctly later.

## 2. Authoritative Area tree

Each Area node has a stable identity and tree relationship. The existing conceptual fields are retained:

- stable Area UID;
- parent UID;
- display name;
- full path;
- depth;
- sibling sort order;
- active/inactive state;
- created/updated timestamps.

The stable node identity is the conceptual authority. Full path text is a derived/compatibility representation used by existing route and report code until all consumers are aligned.

Legacy flat Areas must remain importable without guessing structure. Staff can later move those nodes into the correct hierarchy.

### Unlimited practical nesting

There is no business-level maximum number of Subarea levels.

The implementation may still enforce ordinary technical safety against cycles, invalid parents, duplicate paths, or pathological input, but it must not expose a fixed business rule such as "maximum 4 Subareas."

### Parent/child integrity

- A node cannot become its own parent or a descendant of itself.
- Moving a node moves its entire subtree.
- Renaming/moving a node recalculates descendant full paths.
- Duplicate active full paths are rejected.
- Inactive parents cannot receive new active children unless reactivated through the approved workflow.

## 3. Area Management screen

Use an expandable **Area Tree + Selected Area Details** layout.

### Left panel — Area Tree

The tree shows hierarchy and effective Collector context, for example:

```text
Cardona
  Calahan — Collector A
    Balayong
      Mabini St.
      Riverside
    NIA — Collector B
  San Roque — Collector C
```

The tree provides:

- search by Area or Collector;
- expand/collapse branches;
- `+ Add City/Municipality` at the root;
- `+ Add Barangay` under a City/Municipality;
- `+ Add Subarea` under a Barangay or any deeper Subarea;
- visible effective/inherited Collector context where useful;
- manual sibling ordering.

### Right panel — Selected Area

The selected node shows:

- Area name;
- full path;
- active/inactive state;
- effective Collector;
- whether the Collector is explicit or inherited from an ancestor;
- direct/subtree Client counts as appropriate;
- child/subarea count;
- actions allowed to the current Staff/Management user.

Primary actions:

- Add child Area using the context-appropriate label;
- Assign/Reassign Collector;
- Rename;
- Move;
- Reorder;
- Retire when Management-authorized;
- Reactivate when Management-authorized.

### Authority inside Area Management

For normal Priority #5 operations:

- **Staff/Employee and Management** may create, rename, move, and reorder active Area nodes and may assign/reassign permanent Areas to Collectors through the authenticated/permission-controlled server boundary.
- **Management only** may retire or reactivate an Area. This preserves the separately approved retirement safety rule and is not superseded by the simplified Staff/Management assignment model.
- **Collectors** may not change permanent Area structure or their own permanent Area ownership.

Every meaningful mutation is server-authorized and audited.

### Manual route ordering

Staff/Management can arrange sibling nodes in actual collection order.

Desktop/Web should support drag ordering when practical plus reliable Up/Down controls as a fallback. The stored `sort_order` becomes the route grouping order used by Collector surfaces.

Moving a whole branch preserves the internal order of that branch.

### Move preview

Before a structural move with operational impact, show a concise preview such as:

- Clients affected;
- descendant Areas affected;
- effective Collector changes;
- whether any assignment/delegation becomes stale.

The user confirms once. SPINA performs the change atomically or not at all.

## 4. Collector permanent assignment model

### Who may assign

Staff/Employee and Management may assign/reassign permanent Areas to Collectors through Area Management, subject to the existing authenticated/permission-controlled server boundary.

Collectors cannot change their own permanent Area ownership.

### Parent inheritance

Assigning a Collector to a parent Area includes all descendants by default.

Example:

`Calahan -> Collector A`

Collector A is effective for Calahan and every descendant that does not have a more-specific override.

### Child override

A more-specific child assignment overrides the inherited parent Collector only for that child branch.

Example:

```text
Calahan -> Collector A
  Balayong -> inherited Collector A
  NIA -> Collector B
```

Collector A remains effective for the rest of Calahan. Collector B becomes effective for NIA and its descendants unless a still-deeper override exists.

### Removing an override

If the explicit NIA assignment is removed, NIA falls back automatically to the nearest active inherited parent assignment, e.g. Collector A at Calahan.

### One effective permanent Collector

Parent and child assignment records may coexist, but every candidate Client Area path must resolve to exactly one effective permanent Collector.

The existing `lending.collector_area_owner(...)` rule is the model:

1. find all active parent/ancestor assignments that contain the candidate path;
2. choose the most-specific matching Area;
3. require exactly one Collector at that specificity;
4. if ambiguity remains, fail closed rather than guess.

This protects against duplicate permanent route ownership even while allowing inheritance and overrides.

### Permanent vs delegated access

Temporary delegated Collector access remains separate from permanent Area ownership.

Reassignment or structural movement must invalidate any stale grant that no longer matches the authoritative permanent owner. Existing fail-closed delegated-access behavior remains in force.

## 5. Client Area assignment

### One explicit most-specific operational node

A Client has one current explicit operational Area node at a time.

Example:

`Client -> Balayong`

Because Balayong is under Calahan and Cardona, the Client is visible when Staff/Management views:

- Cardona;
- Calahan;
- Balayong.

That does **not** create three independent Client assignments. The single explicit location is Balayong; ancestors include the Client through hierarchy.

If only the Barangay is known, the Client may temporarily be assigned to the Barangay node. Later it may be refined to a deeper Subarea without creating duplicate permanent ownership.

### Residence is not route assignment

A Client's residential/business/source address must never automatically become Collector routing data.

The Client's current operational node follows the approved collection point and Staff/Management routing decision.

### Permanent Client transfer timing

When moving a Client to another permanent Area/Collector:

- if the Client has **no official collection yet on the transfer date**, the new permanent route becomes effective immediately;
- if the Client **already has an official collection that date**, the new route becomes effective on the next collection day.

SPINA determines the safe effective point automatically. Staff/Management does not choose an arbitrary Immediate/Tomorrow switch.

A Client must never appear as an active permanent route Client for two Collectors at once.

## 6. Area retirement

Used Areas are retired/inactivated, not hard deleted.

Retirement and reactivation are Management-only actions.

Before retirement:

- current Clients under the retiring branch must be reassigned/resolved;
- active permanent Collector dependencies must be resolved;
- the system must prevent retirement if active route ownership would become invalid or ambiguous.

Retired Areas:

- remain available for historical reporting and audit;
- cannot receive new Client or Collector assignments;
- keep historical transactions untouched;
- may be reactivated by Management through the authorized workflow.

Retirement/reactivation and structural moves are audited.

## 7. Collector mobile route

The normal Collector Route is a compact digital daily ledger, not a Client profile screen.

### Main route hierarchy

Show only the operational route hierarchy needed in the field:

`City/Municipality -> Barangay -> Subarea -> deeper Subarea if needed -> Client`

Branches are collapsible/filterable so a Collector with many Areas does not scroll one giant flat list.

The app should remember the last selected/opened route branch after payment/refresh when practical.

### Client row content

The normal route row shows only collection-relevant information:

- Client Name;
- agreed Regular amount;
- agreed 7x7 amount when applicable;
- Advance status/coverage when applicable;
- Past Due status when applicable;
- active operational note from Collector, Staff/Employee, or Management when present;
- the existing collection action such as one-tap Pay.

Do not permanently render on the route row:

- full address;
- ID/Meralco source data;
- residential/business labels;
- collection-location picture;
- unnecessary Client profile information.

### Hidden Client Tools

Tapping the Client opens field tools/details only when needed. Approved hidden tools include:

- collection location + required location picture;
- contact information/call action where allowed;
- payment details and other-amount flow;
- Advance flow;
- Unable to Pay / Past Due reason flow;
- Collector note entry and note history;
- payment/receipt history;
- allowed correction of the Collector's own unremitted entry only;
- renewal/request flow where eligible;
- Client Schedule.

Staff/Management notes are read-only to the Collector. Collector notes follow their own permitted edit lifecycle.

## 8. Collector Client Schedule visibility

Inside `Client Tools -> Schedule`, Collectors may view the current authoritative operational payment schedule.

The schedule is read-only on Collector mobile.

It reflects approved server-side effects such as:

- missed-payment extension;
- catch-up/contraction;
- Advance coverage;
- Past Due state;
- no-collection-day behavior;
- authorized corrections.

### Row-by-row view

Collectors may scroll past and future schedule rows. A row may show:

- date;
- Regular amount/status;
- 7x7 amount/status when applicable;
- Paid / Due / Past Due / Advance-covered / future status.

Tapping a row may show relevant detail such as:

- amount recorded;
- recorder/Collector;
- recorded time;
- Advance coverage;
- Past Due reason;
- note when applicable.

Collectors cannot edit a schedule row directly. Every schedule change must come from the authoritative payment/correction/Advance/Past Due/no-collection-day workflow.

## 9. History, audit, and accounting safety

Current routing changes must never rewrite historical evidence.

Already-recorded collections, receipts, remittances, custody evidence, recorder identity, assigned Collector snapshot, Area snapshot, journal/accounting evidence, and audit history retain the original operational context.

Structural changes affect future/current routing only at the approved effective point.

Meaningful Area actions are auditable, including:

- create;
- rename;
- move;
- reorder;
- retire/reactivate;
- permanent Collector assignment/reassignment/removal;
- Client Area transfer.

Audit records should identify actor, server timestamp, affected node/Client/Collector, prior value, and resulting value without duplicating unnecessary sensitive Client evidence.

## 10. Fail-closed rules

SPINA must reject rather than guess when:

- an Area would become its own ancestor/descendant;
- a duplicate conflicting full path is created;
- a permanent route resolves to two Collectors at the same most-specific level;
- a stale delegated grant no longer belongs to the current permanent owner;
- a structural change would leave an active Client without a valid route when the operation requires one;
- retirement still has unresolved active dependencies;
- a Client transfer would make the Client appear on two permanent routes simultaneously.

The UI should explain the conflict in simple operational language and leave the prior state unchanged.

## 11. Server and compatibility direction

The server/PostgreSQL implementation becomes authoritative for Web/Mobile Area Management and effective Collector ownership.

The existing desktop hierarchy model is the compatibility/design baseline, not a separate source of truth. Existing flat text paths may remain during migration for current reports/routes, but all structural mutations must keep compatibility paths synchronized until those consumers are converted to stable node references.

The existing hierarchical ownership SQL should be preserved conceptually because it already matches the approved parent-inheritance + most-specific-override rule.

No production DB/Auth changes, live Client data, deployment, or merge are authorized by this design approval.

## 12. Acceptance criteria

Priority #5 design is satisfied when the implementation can prove all of the following:

1. Staff/Management can create a City/Barangay/Subarea tree and add children at arbitrary practical depth.
2. Staff/Management can manually reorder sibling Areas and Collector mobile follows that order.
3. Parent Collector assignment includes descendants.
4. A child Collector override removes that child branch from the parent's effective route without deleting the parent assignment.
5. Removing the child override restores inherited ownership.
6. Every active Client Area resolves to one effective permanent Collector or fails closed.
7. A Client explicitly assigned to a deep node appears under its ancestor hierarchy without duplicate Client assignment rows.
8. Client permanent transfer timing follows the no-collection-today / already-collected-today rule.
9. Structural changes do not rewrite historical collection/remittance/custody/accounting evidence.
10. Used Areas retire rather than hard-delete, and retirement/reactivation is Management-only.
11. Collector mobile main route shows hierarchy + compact Client collection information only.
12. Hidden Client Tools can show the approved location/photo and schedule views without cluttering the normal route.
13. Collector schedule rows are view-only and use the existing authoritative schedule engine.
14. Ambiguous ownership, invalid moves, stale grants, and unresolved retirement dependencies fail closed.

## Explicit supersession note

For Priority #5, this approved design supersedes the earlier proposal that required separate City Manager/Area Manager authority roles and role-specific Area-structure ownership.

The current operational rule is intentionally simpler:

- Staff/Employee and Management may perform normal Area organization and assign/reassign Areas to Collectors through authorized Area Management controls;
- Management alone retains retirement/reactivation authority;
- Collector permanent ownership is determined by the Area tree, inheritance, and most-specific override;
- separate managerial geography roles are deferred unless Management later creates a concrete need for them.
