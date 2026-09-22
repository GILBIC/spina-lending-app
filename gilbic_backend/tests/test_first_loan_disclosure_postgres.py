"""R1 register catalog proofs on the guarded disposable onboarding database.

This is the first Task 2 RED slice. Missing register/schema controls must fail
when the existing runner supplies its database, never become a skipped case.
Catalog checks are not behavioral proof of actor/source or race protection;
those insert, replay and concurrency cases belong to subsequent task slices.
"""

import pytest
from psycopg.errors import CheckViolation

from test_client_cif_review_confirmation_postgres import (
    DATABASE_URL,
    connection as connection,
    runtime_url as runtime_url,
)

pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="GILBIC_TEST_DATABASE_URL is not configured"
)
REGISTER = "lending.first_loan_disclosure_calculations"


def _require_register(connection):
    relation = connection.execute(
        "select to_regclass(%s) as relation", (REGISTER,)
    ).fetchone()
    assert relation is not None and relation["relation"] is not None, (
        "R1 Task 2: the private disclosure calculation register is not installed"
    )


def _constraints(connection):
    _require_register(connection)
    return connection.execute(
        """
        select c.contype, c.confrelid::regclass::text as target,
               array(
                   select a.attname::text
                   from unnest(c.conkey) with ordinality as k(attnum, ordinal)
                   join pg_attribute a
                     on a.attrelid = c.conrelid and a.attnum = k.attnum
                   order by k.ordinal
               ) as columns
        from pg_constraint c
        where c.conrelid = to_regclass(%s)
        """,
        (REGISTER,),
    ).fetchall()


def test_register_requires_source_and_private_support_columns(connection):
    _require_register(connection)
    columns = {
        row["column_name"]: row
        for row in connection.execute(
            """
            select column_name, data_type, is_nullable, column_default
            from information_schema.columns
            where table_schema = 'lending'
              and table_name = 'first_loan_disclosure_calculations'
            """
        ).fetchall()
    }
    required = {
        "id": "uuid",
        "request_id": "uuid",
        "application_id": "uuid",
        "application_version_id": "uuid",
        "client_id": "uuid",
        "cif_version_id": "uuid",
        "version_number": "integer",
        "dst_rule_id": "uuid",
        "grt_rule_id": "uuid",
        "request_digest": "text",
        "review_digest": "text",
        "review_snapshot": "jsonb",
        "support_storage_key": "uuid",
        "support_sha256": "text",
        "support_media_type": "text",
        "support_byte_count": "integer",
        "reviewed_by_user_id": "uuid",
        "reviewed_device_id": "uuid",
        "reviewed_at": "timestamp with time zone",
    }
    assert required.keys() <= columns.keys()
    for name, data_type in required.items():
        assert columns[name]["data_type"] == data_type, name
        assert columns[name]["is_nullable"] == "NO", name
    assert columns["reviewed_at"]["column_default"] is not None
    assert columns["supersedes_calculation_id"]["data_type"] == "uuid"
    assert columns["supersedes_calculation_id"]["is_nullable"] == "YES"
    assert not {"ready", "approval_ready", "approved"} & columns.keys()


def test_retry_version_support_and_successor_identities_are_unique(connection):
    keys = {
        tuple(row["columns"])
        for row in _constraints(connection)
        if row["contype"] in ("p", "u")
    }
    assert {
        ("id",),
        ("request_id",),
        ("application_id", "version_number"),
        ("support_storage_key",),
        ("supersedes_calculation_id",),
    } <= keys


def test_register_keeps_foreign_keys_to_real_source_and_review_records(connection):
    references = {
        (tuple(row["columns"]), row["target"])
        for row in _constraints(connection)
        if row["contype"] == "f"
    }
    assert {
        (("application_id",), "lending.loan_applications"),
        (("application_version_id",), "lending.loan_application_versions"),
        (("client_id",), "lending.clients"),
        (("cif_version_id",), "lending.client_cif_versions"),
        (("dst_rule_id",), "accounting.v1_tax_rule_evidence"),
        (("grt_rule_id",), "accounting.v1_tax_rule_evidence"),
        (("reviewed_by_user_id",), "core.users"),
        (("reviewed_device_id",), "core.devices"),
        (("supersedes_calculation_id",), REGISTER),
    } <= references


def test_register_has_enabled_insert_mutation_and_truncate_guards(connection):
    _require_register(connection)
    triggers = connection.execute(
        """
        select tgtype from pg_trigger
        where tgrelid = to_regclass(%s) and not tgisinternal
          and tgenabled in ('O', 'A')
        """,
        (REGISTER,),
    ).fetchall()
    # pg_trigger masks: ROW=1, BEFORE=2, INSERT=4, DELETE=8,
    # UPDATE=16, TRUNCATE=32. Combined trigger events are permitted.
    for required_mask in (1 | 2 | 4, 1 | 2 | 8, 1 | 2 | 16, 2 | 32):
        assert any(
            row["tgtype"] & required_mask == required_mask for row in triggers
        ), f"Missing enabled trigger mask {required_mask}"


def test_register_rejects_truncate_without_disabling_its_guards(connection):
    _require_register(connection)
    with pytest.raises(CheckViolation), connection.transaction():
        connection.execute("truncate lending.first_loan_disclosure_calculations")


def test_register_has_no_public_or_browser_table_grants(connection):
    _require_register(connection)
    public_grants = connection.execute(
        """
        select acl.privilege_type
        from pg_class relation
        cross join lateral aclexplode(
            coalesce(relation.relacl, acldefault('r', relation.relowner))
        ) acl
        where relation.oid = to_regclass(%s) and acl.grantee = 0
        """,
        (REGISTER,),
    ).fetchall()
    assert public_grants == []
    browser_roles = connection.execute(
        "select rolname from pg_roles where rolname in ('anon', 'authenticated')"
    ).fetchall()
    for role in browser_roles:
        for privilege in (
            "SELECT",
            "INSERT",
            "UPDATE",
            "DELETE",
            "TRUNCATE",
            "REFERENCES",
            "TRIGGER",
        ):
            row = connection.execute(
                "select has_table_privilege(%s, %s, %s) as allowed",
                (role["rolname"], REGISTER, privilege),
            ).fetchone()
            assert row is not None and row["allowed"] is False, (
                role["rolname"],
                privilege,
            )
