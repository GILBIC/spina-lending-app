BEGIN;

INSERT INTO core.permissions (code, description)
VALUES
    ('delegated_area.view', 'View delegated Collector area access requests, grants, and granted workspaces'),
    ('delegated_area.request', 'Request temporary access to another Collector''s assigned area scope'),
    ('delegated_area.grant', 'Grant or revoke temporary access to the signed-in Collector''s own assigned area scope')
ON CONFLICT (code) DO UPDATE SET description = EXCLUDED.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM (VALUES
    ('collector', 'delegated_area.view'),
    ('collector', 'delegated_area.request'),
    ('collector', 'delegated_area.grant')
) AS mapping(role_code, permission_code)
JOIN core.roles role ON role.code = mapping.role_code
JOIN core.permissions permission ON permission.code = mapping.permission_code
ON CONFLICT DO NOTHING;

CREATE OR REPLACE FUNCTION lending.normalize_area_path(value TEXT)
RETURNS TEXT
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $$
    SELECT regexp_replace(
        regexp_replace(
            btrim(coalesce(value, '')),
            '[[:space:]]*›[[:space:]]*',
            ' › ',
            'g'
        ),
        '[[:space:]]+',
        ' ',
        'g'
    );
$$;

CREATE OR REPLACE FUNCTION lending.area_path_contains(
    scope_path TEXT,
    candidate_path TEXT,
    include_descendants BOOLEAN DEFAULT false
)
RETURNS BOOLEAN
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $$
    WITH normalized AS (
        SELECT
            lower(lending.normalize_area_path(scope_path)) AS scope_value,
            lower(lending.normalize_area_path(candidate_path)) AS candidate_value
    )
    SELECT
        scope_value <> ''
        AND candidate_value <> ''
        AND (
            candidate_value = scope_value
            OR (
                include_descendants
                AND position(scope_value || ' › ' IN candidate_value) = 1
            )
        )
    FROM normalized;
$$;

CREATE TABLE IF NOT EXISTS lending.collector_area_access_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    requester_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    requested_owner_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    scope_mode TEXT NOT NULL DEFAULT 'selected_paths'
        CHECK (scope_mode IN ('selected_paths', 'all_owner_areas')),
    reason TEXT NOT NULL,
    requested_expires_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'declined', 'cancelled')),
    decided_by_user_id UUID REFERENCES core.users(id) ON DELETE RESTRICT,
    decided_at TIMESTAMPTZ,
    decision_reason TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (requester_user_id <> requested_owner_user_id),
    CHECK (btrim(reason) <> ''),
    CHECK (requested_expires_at > created_at)
);

CREATE INDEX IF NOT EXISTS lending_collector_area_access_request_requester_idx
    ON lending.collector_area_access_requests(requester_user_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS lending_collector_area_access_request_owner_idx
    ON lending.collector_area_access_requests(requested_owner_user_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS lending.collector_area_access_request_scopes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID NOT NULL
        REFERENCES lending.collector_area_access_requests(id) ON DELETE RESTRICT,
    source_assignment_id UUID NOT NULL
        REFERENCES lending.collector_area_assignments(id) ON DELETE RESTRICT,
    area_path TEXT NOT NULL,
    include_descendants BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (btrim(area_path) <> ''),
    UNIQUE (request_id, source_assignment_id)
);

CREATE INDEX IF NOT EXISTS lending_collector_area_access_request_scope_request_idx
    ON lending.collector_area_access_request_scopes(request_id);

CREATE TABLE IF NOT EXISTS lending.collector_area_access_grants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_request_id UUID UNIQUE
        REFERENCES lending.collector_area_access_requests(id) ON DELETE RESTRICT,
    grantor_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    visiting_collector_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    effective_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    revoked_by_user_id UUID REFERENCES core.users(id) ON DELETE RESTRICT,
    revocation_reason TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (grantor_user_id <> visiting_collector_user_id),
    CHECK (expires_at > effective_at),
    CHECK (
        (revoked_at IS NULL AND revoked_by_user_id IS NULL AND revocation_reason = '')
        OR
        (revoked_at IS NOT NULL AND revoked_by_user_id IS NOT NULL AND btrim(revocation_reason) <> '')
    )
);

CREATE INDEX IF NOT EXISTS lending_collector_area_access_grant_visitor_idx
    ON lending.collector_area_access_grants(visiting_collector_user_id, effective_at, expires_at)
    WHERE revoked_at IS NULL;
CREATE INDEX IF NOT EXISTS lending_collector_area_access_grant_grantor_idx
    ON lending.collector_area_access_grants(grantor_user_id, effective_at, expires_at)
    WHERE revoked_at IS NULL;

CREATE TABLE IF NOT EXISTS lending.collector_area_access_grant_scopes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    grant_id UUID NOT NULL
        REFERENCES lending.collector_area_access_grants(id) ON DELETE RESTRICT,
    source_assignment_id UUID NOT NULL
        REFERENCES lending.collector_area_assignments(id) ON DELETE RESTRICT,
    area_path TEXT NOT NULL,
    include_descendants BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (btrim(area_path) <> ''),
    UNIQUE (grant_id, source_assignment_id)
);

CREATE INDEX IF NOT EXISTS lending_collector_area_access_grant_scope_grant_idx
    ON lending.collector_area_access_grant_scopes(grant_id);
CREATE INDEX IF NOT EXISTS lending_collector_area_access_grant_scope_assignment_idx
    ON lending.collector_area_access_grant_scopes(source_assignment_id);

CREATE TABLE IF NOT EXISTS lending.collector_area_access_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID REFERENCES lending.collector_area_access_requests(id) ON DELETE RESTRICT,
    grant_id UUID REFERENCES lending.collector_area_access_grants(id) ON DELETE RESTRICT,
    actor_user_id UUID REFERENCES core.users(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (btrim(event_type) <> ''),
    CHECK (request_id IS NOT NULL OR grant_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS lending_collector_area_access_event_request_idx
    ON lending.collector_area_access_events(request_id, created_at DESC)
    WHERE request_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS lending_collector_area_access_event_grant_idx
    ON lending.collector_area_access_events(grant_id, created_at DESC)
    WHERE grant_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS lending_collector_area_access_event_actor_idx
    ON lending.collector_area_access_events(actor_user_id, created_at DESC)
    WHERE actor_user_id IS NOT NULL;

CREATE OR REPLACE FUNCTION lending.reject_delegated_access_immutable_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Delegated Collector access evidence is immutable; create a new request/grant or revoke the grant instead.';
END;
$$;

DROP TRIGGER IF EXISTS lending_guard_collector_area_access_request_scope_immutable
    ON lending.collector_area_access_request_scopes;
CREATE TRIGGER lending_guard_collector_area_access_request_scope_immutable
BEFORE UPDATE OR DELETE ON lending.collector_area_access_request_scopes
FOR EACH ROW EXECUTE FUNCTION lending.reject_delegated_access_immutable_mutation();

DROP TRIGGER IF EXISTS lending_guard_collector_area_access_grant_scope_immutable
    ON lending.collector_area_access_grant_scopes;
CREATE TRIGGER lending_guard_collector_area_access_grant_scope_immutable
BEFORE UPDATE OR DELETE ON lending.collector_area_access_grant_scopes
FOR EACH ROW EXECUTE FUNCTION lending.reject_delegated_access_immutable_mutation();

DROP TRIGGER IF EXISTS lending_guard_collector_area_access_event_immutable
    ON lending.collector_area_access_events;
CREATE TRIGGER lending_guard_collector_area_access_event_immutable
BEFORE UPDATE OR DELETE ON lending.collector_area_access_events
FOR EACH ROW EXECUTE FUNCTION lending.reject_delegated_access_immutable_mutation();

CREATE OR REPLACE FUNCTION lending.guard_collector_area_access_request_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Delegated area requests are retained as audit evidence; cancel instead of deleting.';
    END IF;

    IF NEW.id IS DISTINCT FROM OLD.id
       OR NEW.requester_user_id IS DISTINCT FROM OLD.requester_user_id
       OR NEW.requested_owner_user_id IS DISTINCT FROM OLD.requested_owner_user_id
       OR NEW.scope_mode IS DISTINCT FROM OLD.scope_mode
       OR NEW.reason IS DISTINCT FROM OLD.reason
       OR NEW.requested_expires_at IS DISTINCT FROM OLD.requested_expires_at
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Delegated area request identity, scope, reason, and requested expiry are immutable.';
    END IF;

    IF OLD.status <> 'pending' AND ROW(NEW.status, NEW.decided_by_user_id, NEW.decided_at, NEW.decision_reason)
        IS DISTINCT FROM ROW(OLD.status, OLD.decided_by_user_id, OLD.decided_at, OLD.decision_reason) THEN
        RAISE EXCEPTION 'A decided delegated area request cannot be changed.';
    END IF;

    IF OLD.status = 'pending' AND NEW.status = 'pending'
       AND ROW(NEW.decided_by_user_id, NEW.decided_at, NEW.decision_reason)
        IS DISTINCT FROM ROW(OLD.decided_by_user_id, OLD.decided_at, OLD.decision_reason) THEN
        RAISE EXCEPTION 'Decision fields cannot change while a delegated area request remains pending.';
    END IF;

    IF NEW.status <> 'pending'
       AND (NEW.decided_by_user_id IS NULL OR NEW.decided_at IS NULL) THEN
        RAISE EXCEPTION 'A decided delegated area request requires decision actor and timestamp.';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lending_guard_collector_area_access_request_update
    ON lending.collector_area_access_requests;
CREATE TRIGGER lending_guard_collector_area_access_request_update
BEFORE UPDATE OR DELETE ON lending.collector_area_access_requests
FOR EACH ROW EXECUTE FUNCTION lending.guard_collector_area_access_request_update();

CREATE OR REPLACE FUNCTION lending.guard_collector_area_access_grant_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Delegated area grants are retained as audit evidence; revoke instead of deleting.';
    END IF;

    IF NEW.id IS DISTINCT FROM OLD.id
       OR NEW.source_request_id IS DISTINCT FROM OLD.source_request_id
       OR NEW.grantor_user_id IS DISTINCT FROM OLD.grantor_user_id
       OR NEW.visiting_collector_user_id IS DISTINCT FROM OLD.visiting_collector_user_id
       OR NEW.effective_at IS DISTINCT FROM OLD.effective_at
       OR NEW.expires_at IS DISTINCT FROM OLD.expires_at
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Delegated area grant identity, participants, and effective window are immutable.';
    END IF;

    IF OLD.revoked_at IS NOT NULL
       AND ROW(NEW.revoked_at, NEW.revoked_by_user_id, NEW.revocation_reason)
        IS DISTINCT FROM ROW(OLD.revoked_at, OLD.revoked_by_user_id, OLD.revocation_reason) THEN
        RAISE EXCEPTION 'A revoked delegated area grant cannot be changed.';
    END IF;

    IF OLD.revoked_at IS NULL AND NEW.revoked_at IS NULL
       AND ROW(NEW.revoked_by_user_id, NEW.revocation_reason)
        IS DISTINCT FROM ROW(OLD.revoked_by_user_id, OLD.revocation_reason) THEN
        RAISE EXCEPTION 'Revocation evidence cannot be set without revoking the delegated area grant.';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS lending_guard_collector_area_access_grant_update
    ON lending.collector_area_access_grants;
CREATE TRIGGER lending_guard_collector_area_access_grant_update
BEFORE UPDATE OR DELETE ON lending.collector_area_access_grants
FOR EACH ROW EXECUTE FUNCTION lending.guard_collector_area_access_grant_update();

CREATE OR REPLACE FUNCTION lending.collector_has_active_delegated_area_access(
    visiting_user_id UUID,
    candidate_area_path TEXT,
    as_of TIMESTAMPTZ DEFAULT now()
)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM lending.collector_area_access_grants grant_record
        JOIN lending.collector_area_access_grant_scopes grant_scope
          ON grant_scope.grant_id = grant_record.id
        JOIN lending.collector_area_assignments source_assignment
          ON source_assignment.id = grant_scope.source_assignment_id
         AND source_assignment.collector_user_id = grant_record.grantor_user_id
         AND source_assignment.is_active = true
         AND lower(lending.normalize_area_path(source_assignment.area)) =
             lower(lending.normalize_area_path(grant_scope.area_path))
        WHERE grant_record.visiting_collector_user_id = visiting_user_id
          AND grant_record.revoked_at IS NULL
          AND grant_record.effective_at <= as_of
          AND grant_record.expires_at > as_of
          AND lending.area_path_contains(
              grant_scope.area_path,
              candidate_area_path,
              grant_scope.include_descendants
          )
          AND grant_record.grantor_user_id = (
              SELECT effective_assignment.collector_user_id
              FROM lending.collector_area_assignments effective_assignment
              WHERE effective_assignment.is_active = true
                AND lending.area_path_contains(
                    effective_assignment.area,
                    candidate_area_path,
                    true
                )
              ORDER BY
                  length(lending.normalize_area_path(effective_assignment.area)) DESC,
                  effective_assignment.sort_order,
                  effective_assignment.id
              LIMIT 1
          )
    );
$$;

COMMIT;
