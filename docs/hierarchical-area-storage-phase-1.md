# Hierarchical Area storage — Phase 1

## Purpose

Prepare SPINA for an unlimited Area hierarchy without breaking the existing flat-text Area workflows.

## New storage

- `area_nodes.area_uid`: stable Area identifier
- `area_nodes.parent_uid`: optional parent identifier
- `area_nodes.name`: one level's name
- `area_nodes.full_path`: complete display path using ` › `
- `area_nodes.depth`: calculated nesting level
- `area_nodes.sort_order`: sibling ordering
- `area_nodes.is_active`: active/inactive state
- `clients.area_uid`: stable link from a client to an Area node

## Compatibility

Phase 1 deliberately keeps these legacy values:

- `clients.area`
- `areas.name`

When a client is assigned through the hierarchy repository, both `clients.area_uid` and the full legacy `clients.area` path are written. Existing Collector Route, Data Bank, reports, filters, and PDFs can therefore continue using Area text while later phases move them to stable IDs.

## Migration

At database initialization:

1. Create `area_nodes` and its indexes if missing.
2. Add `clients.area_uid` if missing.
3. Read all existing `areas.name` and nonblank `clients.area` values.
4. Create one root node for each unique legacy value without changing its text.
5. Backfill blank `clients.area_uid` values.
6. Commit idempotently; repeated startup creates no duplicates.

Legacy strings are not automatically split on dashes or slashes because that could incorrectly change real Area names. Staff will organize existing roots through the future Area Manager.

## Not included yet

- Hierarchical Area Manager screen
- Read-only client Area selector
- Rename, move, arrange, and deactivate UI
- Parent-level Collector Route assignment
- Hierarchical Data Bank grouping

Those are separate phases so the database migration can be tested and rolled back independently.
