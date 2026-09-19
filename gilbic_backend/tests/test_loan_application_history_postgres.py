"""Application storage constraints, not authenticated saving or loan approval.

Reuse the existing guarded disposable database and rollback fixtures. The later
repository must prove atomic saves, retry handling, stale-write rejection and
actor/eligibility checks; direct SQL here does not prove those boundaries.
"""
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from gilbic_backend.loan_application_information import LoanApplicationInformation
from test_client_cif_review_confirmation_postgres import (
    DATABASE_URL,
    _insert as _insert_cif_confirmation,
    _read as _read_cif_confirmation,
    _seed_case,
    _unrelated_counts,
    connection as connection,
    runtime_url as runtime_url,
)


pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="GILBIC_TEST_DATABASE_URL is not configured"
)
TABLES = ("loan_applications", "loan_application_versions")
MIGRATION = (
    Path(__file__).resolve().parents[1] / "sql" / "0120_add_loan_application_history.sql"
)


def _require_schema(connection):
    for table in TABLES:
        relation = connection.execute(
            "select to_regclass(%s) as name", (f"lending.{table}",)
        ).fetchone()["name"]
        assert relation is not None, "Application-history schema is not implemented"


def _header(connection, case, **changes):
    values = {
        "application_reference": f"SYN-APP-{uuid4().hex}",
        "client_id": case["client"],
        "created_by_user_id": case["actor"],
    }
    values.update(changes)
    return connection.execute(
        """
        insert into lending.loan_applications (
            application_reference, client_id, created_by_user_id
        ) values (%(application_reference)s, %(client_id)s, %(created_by_user_id)s)
        returning *
        """, values,
    ).fetchone()


def _version(connection, case, header, **changes):
    values = {
        "application_id": header["id"],
        "client_id": case["client"],
        "cif_version_id": case["cif"],
        "version_number": 1,
        "information": Jsonb(LoanApplicationInformation().model_dump(mode="json")),
        "recorded_by_user_id": case["actor"],
    }
    values.update(changes)
    return connection.execute(
        """
        insert into lending.loan_application_versions (
            application_id, client_id, cif_version_id, version_number,
            information, recorded_by_user_id
        ) values (%(application_id)s, %(client_id)s, %(cif_version_id)s,
                  %(version_number)s, %(information)s, %(recorded_by_user_id)s)
        returning *
        """, values,
    ).fetchone()


def _read(connection, table, record_id):
    return connection.execute(
        sql.SQL("select * from lending.{} where id = %s").format(sql.Identifier(table)),
        (record_id,),
    ).fetchone()


def test_draft_storage_has_server_defaults_and_no_other_state_changes(connection):
    _require_schema(connection)
    case = _seed_case(connection)  # Inactive Client, draft CIF, no Auth identity.
    before = _unrelated_counts(connection)
    for table in TABLES:
        before.pop(f"lending.{table}")
    header = _header(connection, case)
    version = _version(connection, case, header)

    assert set(header) == {
        "id", "application_reference", "client_id", "created_by_user_id", "created_at"
    }
    assert set(version) == {
        "id", "application_id", "client_id", "cif_version_id", "version_number",
        "information", "recorded_by_user_id", "recorded_at"
    }
    assert header["client_id"] == version["client_id"] == case["client"]
    assert version["application_id"] == header["id"]
    assert version["cif_version_id"] == case["cif"]
    assert header["created_by_user_id"] == version["recorded_by_user_id"] == case["actor"]
    now = connection.execute("select now() as now").fetchone()["now"]
    assert header["created_at"] == version["recorded_at"] == now
    assert version["version_number"] == 1
    assert LoanApplicationInformation.model_validate(version["information"]).missing_fields()
    after = _unrelated_counts(connection)
    for table in TABLES:
        after.pop(f"lending.{table}")
    assert after == before
    assert connection.execute(
        "select status, user_id from lending.clients where id = %s", (case["client"],)
    ).fetchone() == {"status": "inactive", "user_id": None}
    assert connection.execute(
        "select status, activated_at from lending.client_cif_versions where id = %s",
        (case["cif"],),
    ).fetchone() == {"status": "draft", "activated_at": None}


def test_new_versions_and_new_applications_reuse_cif_without_rewriting_evidence(connection):
    _require_schema(connection)
    case = _seed_case(connection)
    profile_evidence = _insert_cif_confirmation(connection, case)
    first_header = _header(connection, case)
    original = _version(connection, case, first_header)
    changed = LoanApplicationInformation(request={"requested_amount": "5000.00"})
    second = _version(connection, case, first_header, version_number=2,
                      information=Jsonb(changed.model_dump(mode="json")))
    next_header = _header(connection, case)
    next_loan = _version(connection, case, next_header)

    assert _read(connection, TABLES[1], original["id"]) == original
    assert _read_cif_confirmation(connection, profile_evidence["id"]) == profile_evidence
    assert original["cif_version_id"] == second["cif_version_id"] == next_loan["cif_version_id"]
    assert first_header["id"] != next_header["id"]
    assert next_loan["version_number"] == 1
    assert second["information"]["request"]["requested_amount"] == "5000.00"
    assert LoanApplicationInformation.model_validate(second["information"]) == changed


@pytest.mark.parametrize("duplicate", ["reference", "version"])
def test_duplicate_keys_reject_without_replacing_history(connection, duplicate):
    _require_schema(connection)
    case = _seed_case(connection)
    header = _header(connection, case)
    original = _version(connection, case, header)
    with pytest.raises(psycopg.errors.UniqueViolation):
        with connection.transaction():
            if duplicate == "reference":
                _header(connection, case, application_reference=header["application_reference"])
            else:
                _version(connection, case, header)
    assert _read(connection, TABLES[0], header["id"]) == header
    assert _read(connection, TABLES[1], original["id"]) == original


@pytest.mark.parametrize("target, field", [
    ("header", "client_id"), ("header", "created_by_user_id"),
    ("version", "application_id"), ("version", "client_id"),
    ("version", "cif_version_id"), ("version", "recorded_by_user_id"),
])
def test_nonexistent_references_reject(connection, target, field):
    _require_schema(connection)
    case = _seed_case(connection)
    header = _header(connection, case)
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with connection.transaction():
            if target == "header":
                _header(connection, case, **{field: uuid4()})
            else:
                _version(connection, case, header, **{field: uuid4()})


@pytest.mark.parametrize("mismatch", ["header_client", "cif_client"])
def test_existing_cross_borrower_links_reject(connection, mismatch):
    _require_schema(connection)
    case = _seed_case(connection)
    other = _seed_case(connection)  # Same borrower display name, different UUIDs.
    header = _header(connection, case)
    changes = (
        {"client_id": other["client"], "cif_version_id": other["cif"]}
        if mismatch == "header_client" else {"cif_version_id": other["cif"]}
    )
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with connection.transaction():
            _version(connection, case, header, **changes)


@pytest.mark.parametrize("target, field, value, state", [
    ("header", "application_reference", " ", "23514"),
    ("header", "application_reference", None, "23502"),
    ("header", "client_id", None, "23502"),
    ("header", "created_by_user_id", None, "23502"),
    ("version", "application_id", None, "23502"),
    ("version", "client_id", None, "23502"),
    ("version", "cif_version_id", None, "23502"),
    ("version", "recorded_by_user_id", None, "23502"),
    ("version", "version_number", 0, "23514"),
    ("version", "version_number", -1, "23514"),
    ("version", "version_number", None, "23502"),
    ("version", "information", None, "23502"),
    ("version", "information", Jsonb(None), "23514"),
    ("version", "information", Jsonb([]), "23514"),
    ("version", "information", Jsonb({}), "23514"),
    ("version", "information", Jsonb({"request": {}}), "23514"),
    ("version", "information", Jsonb({"request": {}, "repayment": None}), "23514"),
    ("version", "information", Jsonb({"request": [], "repayment": {}}), "23514"),
    ("version", "information", Jsonb({"request": {}, "repayment": {}, "approved": True}), "23514"),
])
def test_invalid_storage_metadata_or_payload_shape_reject(connection, target, field, value, state):
    _require_schema(connection)
    case = _seed_case(connection)
    header = _header(connection, case)
    with pytest.raises(psycopg.IntegrityError) as rejected:
        with connection.transaction():
            if target == "header":
                _header(connection, case, **{field: value})
            else:
                _version(connection, case, header, **{field: value})
    assert rejected.value.sqlstate == state


@pytest.mark.parametrize("table", TABLES)
@pytest.mark.parametrize("operation", ["update", "delete", "truncate"])
def test_saved_history_rejects_mutation(connection, table, operation):
    _require_schema(connection)
    case = _seed_case(connection)
    header = _header(connection, case)
    version = _version(connection, case, header)
    record = header if table == TABLES[0] else version
    statement = {
        "update": "update lending.{} set client_id = client_id where id = %s",
        "delete": "delete from lending.{} where id = %s",
        "truncate": "truncate lending.{} cascade",
    }[operation]
    # CASCADE reaches both new tables; confined to the guarded disposable DB.
    with pytest.raises(psycopg.errors.CheckViolation, match="Loan application history is immutable"):
        with connection.transaction():
            connection.execute(sql.SQL(statement).format(sql.Identifier(table)),
                               None if operation == "truncate" else (record["id"],))
    assert _read(connection, TABLES[0], header["id"]) == header
    assert _read(connection, TABLES[1], version["id"]) == version


@pytest.mark.parametrize("table", TABLES)
def test_new_tables_have_no_public_or_client_role_grants(connection, table):
    _require_schema(connection)
    grants = connection.execute(
        """
        select acl.grantee, role.rolname
        from pg_class relation
        cross join lateral aclexplode(coalesce(
            relation.relacl, acldefault('r', relation.relowner)
        )) acl
        left join pg_roles role on role.oid = acl.grantee
        where relation.oid = to_regclass(%s)
          and (acl.grantee = 0 or role.rolname in ('anon', 'authenticated', 'service_role'))
        """, (f"lending.{table}",),
    ).fetchall()
    assert grants == []


def test_migration_rerun_preserves_application_and_version_history(runtime_url):
    # Real committed synthetic rows exist only until the runner drops this DB.
    with psycopg.connect(runtime_url, autocommit=True, row_factory=dict_row) as connection:
        _require_schema(connection)
        assert MIGRATION.is_file(), "Application-history migration file is not implemented"
        case = _seed_case(connection)
        header = _header(connection, case)
        version = _version(connection, case, header)
        for _ in range(2):
            connection.execute(MIGRATION.read_text(encoding="utf-8"))
            assert _read(connection, TABLES[0], header["id"]) == header
            assert _read(connection, TABLES[1], version["id"]) == version
        for table, row in ((TABLES[0], header), (TABLES[1], version)):
            with pytest.raises(psycopg.errors.CheckViolation, match="Loan application history is immutable"):
                connection.execute(
                    sql.SQL("delete from lending.{} where id = %s").format(sql.Identifier(table)),
                    (row["id"],),
                )
