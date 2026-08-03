BEGIN;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code IN ('remittance.receive', 'remittance.view')
WHERE role.code = 'collector'
ON CONFLICT DO NOTHING;

COMMENT ON TABLE lending.collection_assignment_reviews IS
    'Acceptance by the assigned collector acts as the review/copy step for a cross-collector payment without duplicating the official transaction.';

COMMIT;
