"""Register behavior in the existing disposable DB, not production approval."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
import test_client_cif_review_confirmation_postgres as cif_proof
import test_first_loan_postgres as first_loan_proof
import test_loan_application_repository_postgres as application_proof
from first_loan_disclosure_fixtures import component_values, review_values
from gilbic_backend.first_loan_disclosure import (
    DisclosureReviewRequest,
    canonical_review_digest,
)
from gilbic_backend.first_loan_terms import (
    generate_first_loan_schedule,
    schedule_payload,
    snapshot_digest,
)
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

runtime_url = cif_proof.runtime_url
connection = cif_proof.connection
private_fixture_configuration = first_loan_proof.private_fixture_configuration
pytestmark = pytest.mark.skipif(
    not cif_proof.DATABASE_URL, reason="GILBIC_TEST_DATABASE_URL is not configured"
)
MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0129_add_first_loan_disclosure_source.sql"
)
REGISTER = "lending.first_loan_disclosure_calculations"


def _rule(connection, actor, tax_type):
    # Synthetic zero treatment tests relationships, never a live exemption.
    return connection.execute(
        """
        select accounting.record_v1_tax_rule_evidence(
            %s, %s, %s, %s, current_date, null, 'exempt', 0, null,
            'SYNTHETIC ONLY', 'SYNTHETIC ONLY', 'SYNTHETIC ONLY',
            %s, 'Synthetic relationship fixture; no live tax decision.', null
        ) as id
        """,
        (actor, uuid4(), tax_type, f"SYN-R1-{uuid4().hex}", "a" * 64),
    ).fetchone()["id"]


def _case(connection, monkeypatch):
    _, repository, case = first_loan_proof.setup(connection, monkeypatch)
    case["dst_rule"] = _rule(connection, case["actor"], "documentary_stamp_tax")
    case["grt_rule"] = _rule(connection, case["actor"], "percentage_tax_lending")
    return repository, case


def _values(connection, case, **changes):
    request = DisclosureReviewRequest.model_validate(
        review_values(
            request_id=changes.get("request_id", uuid4()),
            supersedes_calculation_id=changes.get("supersedes_calculation_id"),
            application_version_id=case["app"].id,
            cif_version_id=case["cif"],
            dst_rule_id=case["dst_rule"],
            grt_rule_id=case["grt_rule"],
            terms=case["terms"],
            components=component_values(
                dst_upfront="0.00",
                total_upfront_deductions="0.00",
                net_proceeds="1000.00",
            ),
            charge_items=[],
            borrower_charge_basis={
                "support_section_reference": "SYNTHETIC section 1",
                "rationale": "Synthetic relationship proof, not tax authority.",
                "dst_zero_reason": "Synthetic company-borne fixture only.",
                "grt_zero_reason": "Synthetic company-borne fixture only.",
            },
        )
    )
    content = base64.b64decode(request.support_base64, validate=True)
    inputs = request.model_dump(mode="json", exclude={"support_base64"})
    source = {
        "application_id": str(case["app"].application_id),
        "application_version_id": str(case["app"].id),
        "client_id": str(case["client"]),
        "cif_version_id": str(case["cif"]),
        "schedule": schedule_payload(generate_first_loan_schedule(request.terms)),
    }
    rules = {}
    for kind in ("dst", "grt"):
        row = connection.execute(
            "select * from accounting.v1_tax_rule_evidence where id = %s",
            (case[f"{kind}_rule"],),
        ).fetchone()
        rules[kind] = json.loads(json.dumps(row, default=str))
    result = {
        "id": uuid4(),
        "request_id": request.request_id,
        "application_id": case["app"].application_id,
        "application_version_id": case["app"].id,
        "client_id": case["client"],
        "cif_version_id": case["cif"],
        "version_number": 1,
        "supersedes_calculation_id": None,
        "dst_rule_id": case["dst_rule"],
        "grt_rule_id": case["grt_rule"],
        "request_digest": canonical_review_digest(inputs),
        "review_digest": snapshot_digest(
            {"input": inputs, "source": source, "rules": rules}
        ),
        "input_snapshot": Jsonb(inputs),
        "source_snapshot": Jsonb(source),
        "rule_snapshot": Jsonb(rules),
        "review_snapshot": Jsonb(inputs),
        "support_storage_key": uuid4(),
        "support_sha256": hashlib.sha256(content).hexdigest(),
        "support_media_type": request.support_media_type,
        "support_byte_count": len(content),
        "reviewed_by_user_id": case["actor"],
        "reviewed_device_id": case["device"],
    }
    result.update(changes)
    return result


def _insert(connection, values):
    return connection.execute(
        sql.SQL("insert into {} ({}) values ({}) returning *").format(
            sql.Identifier("lending", "first_loan_disclosure_calculations"),
            sql.SQL(", ").join(sql.Identifier(key) for key in values),
            sql.SQL(", ").join(sql.Placeholder(key) for key in values),
        ),
        values,
    ).fetchone()


def _counts(connection):
    tables = connection.execute(
        """
        select schemaname, tablename from pg_tables
        where schemaname in ('core', 'lending', 'accounting', 'mobile', 'auth')
          and not (schemaname = 'lending'
                   and tablename = 'first_loan_disclosure_calculations')
        order by schemaname, tablename
        """
    ).fetchall()
    return {
        (row["schemaname"], row["tablename"]): connection.execute(
            sql.SQL("select count(*) as n from {}.{}").format(
                sql.Identifier(row["schemaname"]), sql.Identifier(row["tablename"])
            )
        ).fetchone()["n"]
        for row in tables
    }


def test_review_insert_has_server_time_and_no_other_table_inserts(
    connection, monkeypatch
):
    _, case = _case(connection, monkeypatch)
    values = _values(connection, case, reviewed_at="1999-01-01T00:00:00Z")
    before = _counts(connection)
    assert ("lending", "loans") in before and ("core", "users") in before
    start = connection.execute("select clock_timestamp() as t").fetchone()["t"]
    record = _insert(connection, values)
    end = connection.execute("select clock_timestamp() as t").fetchone()["t"]
    assert start <= record["reviewed_at"] <= end
    assert record["client_id"] == case["client"]
    assert record["request_id"] == values["request_id"]
    assert record["input_snapshot"]["application_version_id"] == str(case["app"].id)
    assert _counts(connection) == before


@pytest.mark.parametrize(
    "field",
    ["client_id", "application_id", "application_version_id", "cif_version_id"],
)
def test_individually_valid_foreign_sources_cannot_be_mixed(
    connection, monkeypatch, field
):
    _, case = _case(connection, monkeypatch)
    _, other = _case(connection, monkeypatch)
    foreign = _values(connection, other)
    values = _values(connection, case, **{field: foreign[field]})
    with pytest.raises(psycopg.errors.CheckViolation):
        with connection.transaction():
            _insert(connection, values)


@pytest.mark.parametrize("field", ["dst_rule_id", "grt_rule_id"])
@pytest.mark.parametrize("kind", ["wrong_type", "missing"])
def test_rule_type_and_existing_identity_are_required(
    connection, monkeypatch, field, kind
):
    _, case = _case(connection, monkeypatch)
    other = case["grt_rule"] if field == "dst_rule_id" else case["dst_rule"]
    values = _values(
        connection, case, **{field: uuid4() if kind == "missing" else other}
    )
    with pytest.raises(psycopg.IntegrityError):
        with connection.transaction():
            _insert(connection, values)


@pytest.mark.parametrize("change", ["foreign_device", "role", "permission"])
def test_reviewer_device_role_and_permission_are_checked(
    connection, monkeypatch, change
):
    _, case = _case(connection, monkeypatch)
    values = _values(connection, case)
    if change == "foreign_device":
        _, other = _case(connection, monkeypatch)
        values["reviewed_device_id"] = other["device"]
    elif change == "role":
        connection.execute(
            "delete from core.user_roles where user_id = %s", (case["actor"],)
        )
    else:
        connection.execute(
            "delete from core.role_permissions "
            "where permission_code = 'lending.first_loan.approve'"
        )
    with pytest.raises(psycopg.errors.CheckViolation):
        with connection.transaction():
            _insert(connection, values)


@pytest.mark.parametrize(
    "field,value",
    [
        ("support_sha256", "not-a-digest"),
        ("support_media_type", "text/html"),
        ("support_byte_count", 0),
        ("support_byte_count", 10485761),
        ("request_digest", "A" * 64),
        ("review_digest", "x"),
        ("input_snapshot", Jsonb([])),
        ("source_snapshot", Jsonb({})),
        ("rule_snapshot", Jsonb(None)),
        ("review_snapshot", Jsonb([])),
    ],
)
def test_invalid_metadata_never_creates_a_partial_record(
    connection, monkeypatch, field, value
):
    _, case = _case(connection, monkeypatch)
    values = _values(connection, case, **{field: value})
    with pytest.raises(psycopg.IntegrityError):
        with connection.transaction():
            _insert(connection, values)
    assert connection.execute(
        "select 1 from lending.first_loan_disclosure_calculations where id = %s",
        (values["id"],),
    ).fetchone() is None


@pytest.mark.parametrize("field", ["request_id", "support_storage_key"])
def test_duplicate_request_or_file_identity_does_not_create_a_successor(
    connection, monkeypatch, field
):
    _, case = _case(connection, monkeypatch)
    first = _insert(connection, _values(connection, case))
    values = _values(
        connection,
        case,
        version_number=2,
        supersedes_calculation_id=first["id"],
        **{field: first[field]},
    )
    with pytest.raises(psycopg.errors.UniqueViolation):
        with connection.transaction():
            _insert(connection, values)


def test_versions_continue_across_corrected_application_versions(
    connection, monkeypatch
):
    _, case = _case(connection, monkeypatch)
    first = _insert(connection, _values(connection, case))
    case["app"] = application_proof._append(
        application_proof._repository(connection, monkeypatch), case, case["app"]
    )
    second = _insert(
        connection,
        _values(
            connection, case, version_number=2, supersedes_calculation_id=first["id"]
        ),
    )
    assert second["application_id"] == first["application_id"]
    assert second["application_version_id"] != first["application_version_id"]
    assert second["version_number"] == 2
    assert second["supersedes_calculation_id"] == first["id"]


@pytest.mark.parametrize("change", ["root", "skip", "foreign", "stale"])
def test_chain_cannot_restart_skip_branch_or_cross_applications(
    connection, monkeypatch, change
):
    _, case = _case(connection, monkeypatch)
    first = _insert(connection, _values(connection, case))
    values = _values(
        connection, case, version_number=2, supersedes_calculation_id=first["id"]
    )
    if change == "root":
        values.update(version_number=1, supersedes_calculation_id=None)
    elif change == "skip":
        values["version_number"] = 3
    elif change == "foreign":
        _, other = _case(connection, monkeypatch)
        foreign = _insert(connection, _values(connection, other))
        values["supersedes_calculation_id"] = foreign["id"]
    else:
        _insert(connection, values)
        values = _values(
            connection, case, version_number=3, supersedes_calculation_id=first["id"]
        )
    with pytest.raises(psycopg.errors.CheckViolation):
        with connection.transaction():
            _insert(connection, values)


@pytest.mark.parametrize("operation", ["update", "delete"])
def test_saved_register_rows_cannot_be_changed(connection, monkeypatch, operation):
    _, case = _case(connection, monkeypatch)
    record = _insert(connection, _values(connection, case))
    command = (
        "update lending.first_loan_disclosure_calculations "
        "set review_digest = %s where id = %s"
        if operation == "update"
        else "delete from lending.first_loan_disclosure_calculations where id = %s"
    )
    params = ("b" * 64, record["id"]) if operation == "update" else (record["id"],)
    with pytest.raises(psycopg.errors.CheckViolation):
        with connection.transaction():
            connection.execute(command, params)
    assert connection.execute(
        "select * from lending.first_loan_disclosure_calculations where id = %s",
        (record["id"],),
    ).fetchone() == record


def _schema_two_approval(connection, case, calculation, **changes):
    loan_id, approval_id = uuid4(), uuid4()
    packet = {
        "schema_version": 2,
        "terms": calculation["input_snapshot"]["terms"],
        "tax_disclosure": {
            "calculation_id": str(calculation["id"]),
            "review_digest": calculation["review_digest"],
        },
    }
    packet.update(changes)
    connection.execute(
        """
        insert into lending.loans(
            id, loan_number, client_id, loan_type_id, principal, daily_amount,
            interest_rate, date_released, due_date, status, created_by_user_id
        ) values (%s, %s, %s, %s, 1000, 100, 20, null, null, 'approved', %s)
        """,
        (
            loan_id,
            f"SYN-R1-{loan_id.hex}",
            case["client"],
            case["terms"]["loan_type_id"],
            case["actor"],
        ),
    )
    return connection.execute(
        """
        insert into lending.first_loan_approvals(
            id, request_id, loan_id, client_id, application_version_id,
            cif_version_id, template_version, packet, packet_hash,
            approved_by_user_id, approved_device_id
        ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        returning *
        """,
        (
            approval_id,
            uuid4(),
            loan_id,
            case["client"],
            case["app"].id,
            case["cif"],
            case["template"],
            Jsonb(packet),
            snapshot_digest(packet),
            case["actor"],
            case["device"],
        ),
    ).fetchone()


@pytest.mark.parametrize("change", ["digest", "missing", "foreign", "terms"])
def test_schema_two_approval_rejects_wrong_binding_atomically(
    connection, monkeypatch, change
):
    _, case = _case(connection, monkeypatch)
    record = _insert(connection, _values(connection, case))
    changes = {}
    if change == "terms":
        changes["terms"] = {**record["input_snapshot"]["terms"], "principal": "1.00"}
    else:
        source_id = str(record["id"])
        digest = record["review_digest"]
        if change == "digest":
            digest = "b" * 64
        elif change == "missing":
            source_id = str(uuid4())
        else:
            _, other = _case(connection, monkeypatch)
            other_record = _insert(connection, _values(connection, other))
            source_id, digest = str(other_record["id"]), other_record["review_digest"]
        changes["tax_disclosure"] = {
            "calculation_id": source_id,
            "review_digest": digest,
        }
    before = _counts(connection)
    with pytest.raises(psycopg.errors.CheckViolation):
        with connection.transaction():
            _schema_two_approval(connection, case, record, **changes)
    assert _counts(connection) == before


def test_schema_two_relationship_accepts_exact_source_not_issuance(
    connection, monkeypatch
):
    _, case = _case(connection, monkeypatch)
    record = _insert(connection, _values(connection, case))
    approval = _schema_two_approval(connection, case, record)
    binding = approval["packet"]["tax_disclosure"]
    assert binding["review_digest"] == record["review_digest"]
    # This is a direct database relationship proof, not the future API's
    # freshness/document readiness or permission to issue a real loan.
    assert connection.execute(
        "select 1 from lending.first_loan_releases where loan_id = %s",
        (approval["loan_id"],),
    ).fetchone() is None


def test_migration_rerun_preserves_committed_review_and_schema_one_packet(
    runtime_url, monkeypatch
):
    # runtime_url verifies the opt-in, loopback and disposable database name.
    # These synthetic records intentionally commit; the runner drops their DB.
    with psycopg.connect(runtime_url, row_factory=dict_row) as database:
        repository, case = _case(database, monkeypatch)
        record = _insert(database, _values(database, case))
        first_loan_proof.approve(repository, case)
        legacy = database.execute(
            "select * from lending.first_loan_approvals where client_id = %s",
            (case["client"],),
        ).fetchone()
        assert legacy["packet"]["schema_version"] == 1
        database.commit()
        database.autocommit = True
        database.execute(MIGRATION.read_text(encoding="utf-8"))
        assert database.execute(
            "select * from lending.first_loan_disclosure_calculations where id = %s",
            (record["id"],),
        ).fetchone() == record
        assert database.execute(
            "select * from lending.first_loan_approvals where id = %s",
            (legacy["id"],),
        ).fetchone() == legacy
        with pytest.raises(psycopg.errors.CheckViolation):
            database.execute(
                "delete from lending.first_loan_disclosure_calculations where id = %s",
                (record["id"],),
            )


@pytest.mark.parametrize("value", [None, "", "not-a-uuid"])
def test_schema_two_invalid_identity_has_a_controlled_conflict(
    connection, monkeypatch, value
):
    _, case = _case(connection, monkeypatch)
    record = _insert(connection, _values(connection, case))
    with pytest.raises(psycopg.errors.CheckViolation):
        with connection.transaction():
            _schema_two_approval(
                connection,
                case,
                record,
                tax_disclosure={
                    "calculation_id": value,
                    "review_digest": record["review_digest"],
                },
            )


def test_superseded_review_cannot_be_consumed_by_a_new_schema_two_approval(
    connection, monkeypatch
):
    _, case = _case(connection, monkeypatch)
    first = _insert(connection, _values(connection, case))
    _insert(
        connection,
        _values(
            connection, case, version_number=2, supersedes_calculation_id=first["id"]
        ),
    )
    with pytest.raises(psycopg.errors.CheckViolation):
        with connection.transaction():
            _schema_two_approval(connection, case, first)


def test_source_snapshot_cannot_contradict_valid_record_columns(
    connection, monkeypatch
):
    _, case = _case(connection, monkeypatch)
    values = _values(
        connection,
        case,
        source_snapshot=Jsonb(
            {
                "application_id": str(case["app"].application_id),
                "application_version_id": str(case["app"].id),
                "client_id": str(uuid4()),
                "cif_version_id": str(case["cif"]),
            }
        ),
    )
    with pytest.raises(psycopg.errors.CheckViolation):
        with connection.transaction():
            _insert(connection, values)
