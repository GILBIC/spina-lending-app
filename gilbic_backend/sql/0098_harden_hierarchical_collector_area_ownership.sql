BEGIN;

-- Resolve the authoritative Collector for a client Area path. Permanent
-- assignments own their descendants, but the most-specific active assignment
-- wins. If two different Collectors own the same most-specific path, return
-- NULL so collection and delegation fail closed instead of guessing.
CREATE OR REPLACE FUNCTION lending.collector_area_owner(candidate_area_path TEXT)
RETURNS UUID
LANGUAGE sql
STABLE
AS $$
    WITH matching AS (
        SELECT
            assignment.collector_user_id,
            char_length(lending.normalize_area_path(assignment.area)) AS specificity
        FROM lending.collector_area_assignments assignment
        WHERE assignment.is_active = true
          AND lending.area_path_contains(
              assignment.area,
              candidate_area_path,
              true
          )
    ),
    most_specific AS (
        SELECT matching.collector_user_id
        FROM matching
        WHERE matching.specificity = (
            SELECT max(other.specificity)
            FROM matching other
        )
    )
    SELECT CASE
        WHEN count(DISTINCT most_specific.collector_user_id) = 1
            THEN max(most_specific.collector_user_id::text)::uuid
        ELSE NULL
    END
    FROM most_specific;
$$;

CREATE OR REPLACE FUNCTION lending.collector_owns_area_path(
    collector_user_id UUID,
    candidate_area_path TEXT
)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
AS $$
    SELECT coalesce(
        lending.collector_area_owner(candidate_area_path) = collector_user_id,
        false
    );
$$;

-- A delegated grant is valid only while the grantor is still the authoritative
-- owner of the candidate path. This prevents a parent-area grant from silently
-- following a sub-area after that sub-area is reassigned to another Collector.
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
        JOIN lending.collector_area_assignments assignment
          ON assignment.id = grant_scope.source_assignment_id
         AND assignment.collector_user_id = grant_record.grantor_user_id
         AND assignment.is_active = true
         AND lower(lending.normalize_area_path(assignment.area)) =
             lower(lending.normalize_area_path(grant_scope.area_path))
        WHERE grant_record.visiting_collector_user_id = visiting_user_id
          AND grant_record.revoked_at IS NULL
          AND grant_record.effective_at <= as_of
          AND grant_record.expires_at > as_of
          AND lending.collector_area_owner(candidate_area_path) =
              grant_record.grantor_user_id
          AND lending.area_path_contains(
              grant_scope.area_path,
              candidate_area_path,
              grant_scope.include_descendants
          )
    );
$$;

-- Replace the legacy exact-text assignment capture with hierarchical,
-- most-specific ownership. Existing immutable transactions are intentionally
-- untouched; this affects only new collection transactions.
CREATE OR REPLACE FUNCTION lending.capture_collection_assignment()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, lending, core
AS $$
DECLARE
    client_area TEXT;
    route_owner UUID;
    actor_is_management BOOLEAN;
BEGIN
    SELECT coalesce(client.area, '')
    INTO client_area
    FROM lending.clients client
    WHERE client.id = NEW.client_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'The client for this collection does not exist.'
            USING ERRCODE = '23503';
    END IF;

    route_owner := lending.collector_area_owner(client_area);

    SELECT EXISTS (
        SELECT 1
        FROM core.user_roles user_role
        JOIN core.roles role ON role.id = user_role.role_id
        WHERE user_role.user_id = NEW.collector_user_id
          AND role.code = 'management'
    )
    INTO actor_is_management;

    NEW.assignment_area := client_area;
    NEW.assigned_collector_user_id := route_owner;

    IF actor_is_management THEN
        NEW.collection_origin := 'management_direct';
    ELSIF route_owner IS NULL THEN
        NEW.collection_origin := 'unassigned_intake';
    ELSIF route_owner = NEW.collector_user_id THEN
        NEW.collection_origin := 'assigned_route';
    ELSE
        NEW.collection_origin := 'cross_collector';
    END IF;

    RETURN NEW;
END;
$$;

COMMIT;
