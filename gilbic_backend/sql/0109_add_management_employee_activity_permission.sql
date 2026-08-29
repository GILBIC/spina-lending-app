BEGIN;

INSERT INTO core.permissions (code, description)
VALUES (
    'employee.activity.review',
    'Review permission-scoped Employee work evidence without gaining domain action authority'
)
ON CONFLICT (code) DO UPDATE SET description = EXCLUDED.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM (VALUES
    ('management', 'employee.activity.review')
) AS mapping(role_code, permission_code)
JOIN core.roles role ON role.code = mapping.role_code
JOIN core.permissions permission ON permission.code = mapping.permission_code
ON CONFLICT DO NOTHING;

COMMIT;
