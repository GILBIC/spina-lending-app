begin;

insert into core.permissions (code, description)
values (
    'client.credential.manage',
    'Generate replacement credentials for Client accounts'
)
on conflict (code) do update set description = excluded.description;

insert into core.role_permissions (role_id, permission_code)
select r.id, p.code
from (values
    ('employee', 'client.credential.manage'),
    ('management', 'client.credential.manage')
) as mapping(role_code, permission_code)
join core.roles r on r.code = mapping.role_code
join core.permissions p on p.code = mapping.permission_code
on conflict do nothing;

commit;
