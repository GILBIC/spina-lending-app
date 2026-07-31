begin;

insert into core.permissions (code, description)
values
    ('account.manage', 'Manage Gilbic user accounts and role assignments'),
    ('device.manage', 'View and manage registered Gilbic devices')
on conflict (code) do update set description = excluded.description;

insert into core.role_permissions (role_id, permission_code)
select r.id, p.code
from (values
    ('management', 'account.manage'),
    ('management', 'device.manage')
) as mapping(role_code, permission_code)
join core.roles r on r.code = mapping.role_code
join core.permissions p on p.code = mapping.permission_code
on conflict do nothing;

create table if not exists core.audit_logs (
    id uuid primary key default gen_random_uuid(),
    actor_user_id uuid references core.users(id) on delete set null,
    action text not null,
    target_type text not null,
    target_id uuid,
    details jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    check (btrim(action) <> ''),
    check (btrim(target_type) <> '')
);

create index if not exists core_audit_logs_actor_idx
    on core.audit_logs(actor_user_id);
create index if not exists core_audit_logs_target_idx
    on core.audit_logs(target_type, target_id);
create index if not exists core_audit_logs_created_idx
    on core.audit_logs(created_at desc);

commit;
