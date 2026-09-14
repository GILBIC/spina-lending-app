BEGIN;

CREATE TABLE IF NOT EXISTS lending.area_nodes (
    area_uid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_area_uid UUID REFERENCES lending.area_nodes(area_uid) ON DELETE RESTRICT,
    name TEXT NOT NULL,
    full_path TEXT NOT NULL,
    depth INTEGER NOT NULL DEFAULT 0 CHECK (depth >= 0),
    sort_order INTEGER NOT NULL DEFAULT 0 CHECK (sort_order >= 0),
    is_active BOOLEAN NOT NULL DEFAULT true,
    is_legacy_unmapped BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (btrim(name) <> ''),
    CHECK (btrim(full_path) <> '')
);

CREATE UNIQUE INDEX IF NOT EXISTS lending_area_nodes_full_path_lower_uidx
    ON lending.area_nodes (lower(lending.normalize_area_path(full_path)));
CREATE INDEX IF NOT EXISTS lending_area_nodes_parent_order_idx
    ON lending.area_nodes(parent_area_uid, sort_order, lower(name));

ALTER TABLE lending.clients
    ADD COLUMN IF NOT EXISTS area_uid UUID
        REFERENCES lending.area_nodes(area_uid) ON DELETE RESTRICT;
ALTER TABLE lending.collector_area_assignments
    ADD COLUMN IF NOT EXISTS area_uid UUID
        REFERENCES lending.area_nodes(area_uid) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS lending_clients_area_uid_idx
    ON lending.clients(area_uid)
    WHERE area_uid IS NOT NULL;
CREATE INDEX IF NOT EXISTS lending_collector_area_area_uid_idx
    ON lending.collector_area_assignments(area_uid)
    WHERE area_uid IS NOT NULL;

-- Existing flat route text is migrated as whole, unmapped root nodes. SPINA does
-- not infer official or operational parentage from legacy display/address text.
WITH legacy_paths AS (
    SELECT
        lending.normalize_area_path(client.area) AS normalized_path,
        0::integer AS source_sort_order
    FROM lending.clients client
    WHERE lending.normalize_area_path(client.area) <> ''

    UNION ALL

    SELECT
        lending.normalize_area_path(assignment.area) AS normalized_path,
        assignment.sort_order AS source_sort_order
    FROM lending.collector_area_assignments assignment
    WHERE lending.normalize_area_path(assignment.area) <> ''
),
legacy_roots AS (
    SELECT
        lower(normalized_path) AS normalized_key,
        min(normalized_path) AS full_path,
        min(source_sort_order) AS sort_order
    FROM legacy_paths
    GROUP BY lower(normalized_path)
)
INSERT INTO lending.area_nodes (
    parent_area_uid,
    name,
    full_path,
    depth,
    sort_order,
    is_active,
    is_legacy_unmapped
)
SELECT
    NULL,
    legacy_root.full_path,
    legacy_root.full_path,
    0,
    legacy_root.sort_order,
    true,
    true
FROM legacy_roots legacy_root
WHERE NOT EXISTS (
    SELECT 1
    FROM lending.area_nodes existing
    WHERE lower(lending.normalize_area_path(existing.full_path)) =
          legacy_root.normalized_key
)
ON CONFLICT DO NOTHING;

UPDATE lending.clients client
SET area_uid = node.area_uid
FROM lending.area_nodes node
WHERE client.area_uid IS NULL
  AND lending.normalize_area_path(client.area) <> ''
  AND lower(lending.normalize_area_path(client.area)) =
      lower(lending.normalize_area_path(node.full_path));

UPDATE lending.collector_area_assignments assignment
SET area_uid = node.area_uid
FROM lending.area_nodes node
WHERE assignment.area_uid IS NULL
  AND lending.normalize_area_path(assignment.area) <> ''
  AND lower(lending.normalize_area_path(assignment.area)) =
      lower(lending.normalize_area_path(node.full_path));

-- Fail closed before adding the one-active-owner-per-node invariant. This also
-- catches duplicate active rows for one node so migration never silently picks
-- a permanent assignment record.
DO $$
DECLARE
    conflicting_area_uid UUID;
    conflicting_owner_count INTEGER;
    conflicting_row_count INTEGER;
BEGIN
    SELECT
        assignment.area_uid,
        count(DISTINCT assignment.collector_user_id)::integer,
        count(*)::integer
    INTO
        conflicting_area_uid,
        conflicting_owner_count,
        conflicting_row_count
    FROM lending.collector_area_assignments assignment
    WHERE assignment.is_active = true
      AND assignment.area_uid IS NOT NULL
    GROUP BY assignment.area_uid
    HAVING count(*) > 1
    ORDER BY assignment.area_uid
    LIMIT 1;

    IF conflicting_area_uid IS NOT NULL THEN
        RAISE EXCEPTION
            'Area % has % active permanent assignment rows across % Collector(s); resolve the conflict before Area Management migration.',
            conflicting_area_uid,
            conflicting_row_count,
            conflicting_owner_count;
    END IF;
END;
$$;

CREATE UNIQUE INDEX IF NOT EXISTS lending_collector_active_area_uid_uidx
    ON lending.collector_area_assignments(area_uid)
    WHERE is_active = true and area_uid is not null;

CREATE TABLE IF NOT EXISTS lending.client_area_pending_transfers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES lending.clients(id) ON DELETE RESTRICT,
    current_area_uid UUID REFERENCES lending.area_nodes(area_uid) ON DELETE RESTRICT,
    current_area_path_snapshot TEXT NOT NULL DEFAULT '',
    target_area_uid UUID NOT NULL REFERENCES lending.area_nodes(area_uid) ON DELETE RESTRICT,
    target_area_path_snapshot TEXT NOT NULL,
    effective_date DATE NOT NULL,
    scheduled_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    scheduled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    applied_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    cancelled_by_user_id UUID REFERENCES core.users(id) ON DELETE RESTRICT,
    cancellation_reason TEXT NOT NULL DEFAULT '',
    CHECK (btrim(target_area_path_snapshot) <> ''),
    CHECK (NOT (applied_at IS NOT NULL AND cancelled_at IS NOT NULL)),
    CHECK (
        cancelled_at IS NULL
        OR cancelled_by_user_id IS NOT NULL
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS lending_client_area_one_pending_uidx
    ON lending.client_area_pending_transfers(client_id)
    WHERE applied_at IS NULL AND cancelled_at IS NULL;
CREATE INDEX IF NOT EXISTS lending_client_area_pending_effective_idx
    ON lending.client_area_pending_transfers(effective_date, client_id)
    WHERE applied_at IS NULL AND cancelled_at IS NULL;
CREATE INDEX IF NOT EXISTS lending_client_area_pending_target_idx
    ON lending.client_area_pending_transfers(target_area_uid)
    WHERE applied_at IS NULL AND cancelled_at IS NULL;

CREATE TABLE IF NOT EXISTS lending.client_area_transfer_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pending_transfer_id UUID REFERENCES lending.client_area_pending_transfers(id) ON DELETE RESTRICT,
    client_id UUID NOT NULL REFERENCES lending.clients(id) ON DELETE RESTRICT,
    old_area_uid UUID REFERENCES lending.area_nodes(area_uid) ON DELETE RESTRICT,
    old_area_path_snapshot TEXT NOT NULL DEFAULT '',
    new_area_uid UUID NOT NULL REFERENCES lending.area_nodes(area_uid) ON DELETE RESTRICT,
    new_area_path_snapshot TEXT NOT NULL,
    effective_date DATE NOT NULL,
    timing TEXT NOT NULL CHECK (timing IN ('immediate', 'next_collection_day')),
    scheduled_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    scheduled_at TIMESTAMPTZ NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (btrim(new_area_path_snapshot) <> '')
);

CREATE INDEX IF NOT EXISTS lending_client_area_transfer_history_client_idx
    ON lending.client_area_transfer_history(client_id, applied_at DESC);
CREATE INDEX IF NOT EXISTS lending_client_area_transfer_history_area_idx
    ON lending.client_area_transfer_history(new_area_uid, applied_at DESC);

CREATE OR REPLACE FUNCTION lending.reject_client_area_transfer_history_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Client Area transfer history is immutable; record a new transfer instead.';
END;
$$;

DROP TRIGGER IF EXISTS lending_guard_client_area_transfer_history_immutable
    ON lending.client_area_transfer_history;
CREATE TRIGGER lending_guard_client_area_transfer_history_immutable
BEFORE UPDATE OR DELETE ON lending.client_area_transfer_history
FOR EACH ROW EXECUTE FUNCTION lending.reject_client_area_transfer_history_mutation();

INSERT INTO core.permissions (code, description)
VALUES
    ('area.manage', 'Create, rename, move, and reorder active Areas'),
    ('area.collector.assign', 'Assign permanent Areas to Collectors'),
    ('area.client.assign', 'Assign a Client current operational Area'),
    ('area.retire', 'Retire or reactivate an Area')
ON CONFLICT (code) DO UPDATE SET description = EXCLUDED.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM (VALUES
    ('employee', 'area.manage'),
    ('management', 'area.manage'),
    ('employee', 'area.collector.assign'),
    ('management', 'area.collector.assign'),
    ('employee', 'area.client.assign'),
    ('management', 'area.client.assign'),
    ('management', 'area.retire')
) AS mapping(role_code, permission_code)
JOIN core.roles role ON role.code = mapping.role_code
JOIN core.permissions permission ON permission.code = mapping.permission_code
ON CONFLICT DO NOTHING;

COMMIT;
