BEGIN;

-- Preparation only; existing Management journal review/post authority is unchanged.
INSERT INTO core.permissions(code,description) VALUES
 ('cash_disbursement.prepare','Prepare constrained expense-to-cash journal drafts for Management review')
ON CONFLICT(code) DO UPDATE SET description=EXCLUDED.description;
INSERT INTO core.role_permissions(role_id,permission_code)
 SELECT role.id,'cash_disbursement.prepare' FROM core.roles role
 WHERE role.code IN ('employee','management')
ON CONFLICT DO NOTHING;

COMMIT;
