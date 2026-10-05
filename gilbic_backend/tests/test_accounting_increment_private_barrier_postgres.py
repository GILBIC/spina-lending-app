"""Every new accounting evidence object stays outside direct client grants."""

import os
import re

from test_source_close_guard_postgres import _connect
from test_treasury_receipt_accounting_postgres import SQL_ROOT


def _declared_names(kind):
    names = set()
    through = int(os.getenv("SPINA_CURRENT_SCHEMA_THROUGH", "154"))
    for path in SQL_ROOT.glob("*.sql"):
        if 142 <= int(path.name.split("_", 1)[0]) <= through:
            names.update(
                re.findall(
                    rf"CREATE\s+(?:OR\s+REPLACE\s+)?{kind}\s+(?:IF\s+NOT\s+EXISTS\s+)?accounting\.([a-z_0-9]+)",
                    path.read_text(encoding="utf-8"),
                    flags=re.IGNORECASE,
                )
            )
    return sorted(names)


def test_all_accounting_increment_functions_deny_public_and_client_execution():
    names = _declared_names("FUNCTION")
    assert names
    with _connect() as conn:
        rows = conn.execute(
            "SELECT p.proname,p.oid FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
            "WHERE n.nspname='accounting' AND p.proname=ANY(%s)",
            (names,),
        ).fetchall()
        assert set(names) == {row[0] for row in rows}, (
            "Run this barrier on the full current schema"
        )
        oids = [row[1] for row in rows]
        assert (
            conn.execute(
                "SELECT p.oid::regprocedure FROM pg_proc p, "
                "LATERAL aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) acl "
                "WHERE p.oid=ANY(%s) AND acl.grantee=0 AND acl.privilege_type='EXECUTE'",
                (oids,),
            ).fetchall()
            == []
        )
        assert (
            conn.execute(
                "SELECT r.rolname,p.oid::regprocedure FROM pg_roles r CROSS JOIN pg_proc p "
                "WHERE r.rolname IN('anon','authenticated','service_role') AND p.oid=ANY(%s) "
                "AND has_function_privilege(r.oid,p.oid,'EXECUTE')",
                (oids,),
            ).fetchall()
            == []
        )


def test_all_accounting_increment_tables_and_views_deny_direct_client_access():
    names = sorted(set(_declared_names("TABLE") + _declared_names("VIEW")))
    assert names
    with _connect() as conn:
        rows = conn.execute(
            "SELECT c.relname,c.oid,c.relkind,c.relrowsecurity FROM pg_class c "
            "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='accounting' "
            "AND c.relname=ANY(%s)",
            (names,),
        ).fetchall()
        assert set(names) == {row[0] for row in rows}, (
            "Run this barrier on the full current schema"
        )
        assert all(row[3] for row in rows if row[2] == "r"), (
            "Private evidence tables require RLS"
        )
        oids = [row[1] for row in rows]
        assert (
            conn.execute(
                "SELECT c.oid::regclass FROM pg_class c, "
                "LATERAL aclexplode(coalesce(c.relacl,acldefault('r',c.relowner))) acl "
                "WHERE c.oid=ANY(%s) AND acl.grantee=0",
                (oids,),
            ).fetchall()
            == []
        )
        assert (
            conn.execute(
                "SELECT r.rolname,c.oid::regclass FROM pg_roles r CROSS JOIN pg_class c "
                "WHERE r.rolname IN('anon','authenticated','service_role') AND c.oid=ANY(%s) "
                "AND has_table_privilege(r.oid,c.oid,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')",
                (oids,),
            ).fetchall()
            == []
        )
