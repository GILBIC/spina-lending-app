from __future__ import annotations

import os
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from tools import run_stage5d17_disposable_postgres_validation as disposable


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="GILBIC_TEST_DATABASE_URL is not configured"
)
MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0119_add_client_cif_review_confirmation.sql"
)


@pytest.fixture(scope="module")
def runtime_url() -> str:
    # These tests include TRUNCATE rejection and a committed migration rerun.
    # Only the existing runner's explicitly disposable, loopback DB is allowed.
    if os.getenv("SPINA_ALLOW_DISPOSABLE_DATABASE") != "1":
        raise RuntimeError("CIF proof requires SPINA_ALLOW_DISPOSABLE_DATABASE=1")
    assert DATABASE_URL is not None
    params = disposable._safe_local_connection_params(DATABASE_URL)
    if not re.fullmatch(r"spina_onboarding_[0-9a-f]{12}", params["dbname"]):
        raise RuntimeError("CIF proof requires the onboarding disposable database")
    disposable._clear_endpoint_environment()
    return make_conninfo(**params)


@pytest.fixture
def connection(runtime_url: str) -> Iterator[psycopg.Connection]:
    connection = psycopg.connect(runtime_url, row_factory=dict_row)
    try:
        row = connection.execute(
            "select to_regclass('lending.client_cif_review_confirmations') as relation"
        ).fetchone()
        assert row["relation"] is not None, "Runner must apply CIF migrations 0114/0119"
        yield connection
    finally:
        # Roll back test data instead of disabling immutable-evidence triggers.
        connection.rollback()
        connection.close()


def _seed_case(connection: psycopg.Connection) -> dict[str, UUID]:
    case = {key: uuid4() for key in ("actor", "client", "other", "cif", "next_cif")}
    connection.execute(
        "insert into core.users (id, username, full_name) values (%s, %s, %s)",
        (case["actor"], f"cif-proof-{case['actor'].hex}", "Synthetic CIF Witness"),
    )
    for client_id in (case["client"], case["other"]):
        connection.execute(
            """
            insert into lending.clients (id, client_code, full_name, status)
            values (%s, %s, 'Synthetic CIF Borrower', 'inactive')
            """,
            (client_id, f"SYN-CIF-{client_id.hex}"),
        )
    for version, key in ((1, "cif"), (2, "next_cif")):
        connection.execute(
            """
            insert into lending.client_cif_versions (
                id, client_id, version_number, is_current,
                full_name, phone_number, present_address
            ) values (%s, %s, %s, %s, 'Synthetic CIF Borrower',
                      '00000000000', 'Synthetic office test address')
            """,
            (case[key], case["client"], version, version == 1),
        )
    return case


def _insert(
    connection: psycopg.Connection, case: dict[str, UUID], **overrides: Any
) -> dict[str, Any]:
    values = {
        "client_id": case["client"],
        "cif_version_id": case["cif"],
        "review_cycle_number": 1,
        "review_snapshot": Jsonb({"full_name": "Synthetic CIF Borrower"}),
        "applicant_confirmation_evidence_reference": "SYNTHETIC-CIF-CONFIRMATION",
        "witnessed_by_user_id": case["actor"],
    }
    values.update(overrides)
    return connection.execute(
        """
        insert into lending.client_cif_review_confirmations (
            client_id, cif_version_id, review_cycle_number, review_snapshot,
            applicant_confirmation_evidence_reference, witnessed_by_user_id
        ) values (%(client_id)s, %(cif_version_id)s, %(review_cycle_number)s,
                  %(review_snapshot)s, %(applicant_confirmation_evidence_reference)s,
                  %(witnessed_by_user_id)s)
        returning *
        """,
        values,
    ).fetchone()


def _read(connection: psycopg.Connection, record_id: UUID) -> dict[str, Any]:
    return connection.execute(
        "select * from lending.client_cif_review_confirmations where id = %s",
        (record_id,),
    ).fetchone()


def _unrelated_counts(connection: psycopg.Connection) -> dict[str, int]:
    tables = connection.execute(
        """
        select schemaname, tablename from pg_tables
        where schemaname in ('core', 'lending', 'accounting', 'mobile', 'auth')
          and not (schemaname = 'lending' and tablename = 'client_cif_review_confirmations')
        order by schemaname, tablename
        """
    ).fetchall()
    return {
        f"{table['schemaname']}.{table['tablename']}": connection.execute(
            sql.SQL("select count(*) as count from {}.{}").format(
                sql.Identifier(table["schemaname"]), sql.Identifier(table["tablename"])
            )
        ).fetchone()["count"]
        for table in tables
    }


def test_valid_confirmation_has_server_time_and_no_new_financial_rows(connection) -> None:
    case = _seed_case(connection)
    before = _unrelated_counts(connection)
    assert {"auth.users", "core.users", "lending.clients", "lending.loans"} <= before.keys()
    row = _insert(connection, case)
    assert row["client_id"] == case["client"]
    assert row["cif_version_id"] == case["cif"]
    assert row["witnessed_by_user_id"] == case["actor"]
    assert row["review_cycle_number"] == 1
    assert row["review_snapshot"] == {"full_name": "Synthetic CIF Borrower"}
    assert row["applicant_confirmation_evidence_reference"] == "SYNTHETIC-CIF-CONFIRMATION"
    assert row["confirmed_at"] == connection.execute("select now() as now").fetchone()["now"]
    assert _unrelated_counts(connection) == before
    client = connection.execute(
        "select status, user_id from lending.clients where id = %s", (case["client"],)
    ).fetchone()
    assert client == {"status": "inactive", "user_id": None}
    cif = connection.execute(
        "select status, activated_at from lending.client_cif_versions where id = %s",
        (case["cif"],),
    ).fetchone()
    assert cif == {"status": "draft", "activated_at": None}


@pytest.mark.parametrize("duplicate", ["cif_version", "client_cycle"])
def test_duplicate_confirmation_is_rejected_without_overwriting(connection, duplicate) -> None:
    case = _seed_case(connection)
    first = _insert(connection, case)
    override = (
        {"review_cycle_number": 2}
        if duplicate == "cif_version"
        else {"cif_version_id": case["next_cif"]}
    )
    with pytest.raises(psycopg.errors.UniqueViolation):
        with connection.transaction():
            _insert(connection, case, **override)
    assert _read(connection, first["id"]) == first


def test_new_version_and_review_cycle_preserve_previous_confirmation(connection) -> None:
    case = _seed_case(connection)
    first = _insert(connection, case)
    second = _insert(connection, case, cif_version_id=case["next_cif"], review_cycle_number=2)
    assert first["id"] != second["id"]
    assert _read(connection, first["id"]) == first


@pytest.mark.parametrize("field", ["client_id", "cif_version_id", "witnessed_by_user_id"])
def test_missing_reference_is_rejected(connection, field) -> None:
    case = _seed_case(connection)
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with connection.transaction():
            _insert(connection, case, **{field: uuid4()})


def test_existing_but_mismatched_client_and_cif_are_rejected(connection) -> None:
    case = _seed_case(connection)
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with connection.transaction():
            _insert(connection, case, client_id=case["other"])


@pytest.mark.parametrize(
    "field,value,sqlstate",
    [
        ("review_cycle_number", 0, "23514"),
        ("review_cycle_number", -1, "23514"),
        ("review_cycle_number", None, "23502"),
        ("applicant_confirmation_evidence_reference", "", "23514"),
        ("applicant_confirmation_evidence_reference", "   ", "23514"),
        ("applicant_confirmation_evidence_reference", None, "23502"),
        ("review_snapshot", None, "23502"),
        ("review_snapshot", Jsonb({}), "23514"),
        ("review_snapshot", Jsonb([]), "23514"),
        ("review_snapshot", Jsonb("not an object"), "23514"),
        ("review_snapshot", Jsonb(None), "23514"),
        ("witnessed_by_user_id", None, "23502"),
        ("client_id", None, "23502"),
        ("cif_version_id", None, "23502"),
    ],
)
def test_invalid_confirmation_is_rejected(connection, field, value, sqlstate) -> None:
    case = _seed_case(connection)
    with pytest.raises(psycopg.IntegrityError) as rejected:
        with connection.transaction():
            _insert(connection, case, **{field: value})
    assert rejected.value.sqlstate == sqlstate
    count = connection.execute(
        "select count(*) as count from lending.client_cif_review_confirmations where client_id = %s",
        (case["client"],),
    ).fetchone()["count"]
    assert count == 0


@pytest.mark.parametrize("operation", ["update", "delete", "truncate"])
def test_confirmation_mutations_are_rejected(connection, operation) -> None:
    case = _seed_case(connection)
    first = _insert(connection, case)
    statements = {
        "update": (
            "update lending.client_cif_review_confirmations "
            "set review_snapshot = '{\"tampered\":true}'::jsonb where id = %s",
            (first["id"],),
        ),
        "delete": ("delete from lending.client_cif_review_confirmations where id = %s", (first["id"],)),
        "truncate": ("truncate lending.client_cif_review_confirmations", None),
    }
    statement, params = statements[operation]
    with pytest.raises(psycopg.errors.CheckViolation, match="CIF review confirmations are immutable"):
        with connection.transaction():
            connection.execute(statement, params)
    assert _read(connection, first["id"]) == first


def test_migration_rerun_preserves_confirmation_and_guards(runtime_url) -> None:
    # Deliberately committed synthetic data remains only until the runner drops
    # this entire disposable DB. Never disable triggers to clean up evidence.
    with psycopg.connect(runtime_url, autocommit=True, row_factory=dict_row) as connection:
        case = _seed_case(connection)
        first = _insert(connection, case)
        migration_sql = MIGRATION.read_text(encoding="utf-8")
        for _ in range(2):
            connection.execute(migration_sql)
            assert _read(connection, first["id"]) == first
        with pytest.raises(psycopg.errors.CheckViolation, match="CIF review confirmations are immutable"):
            connection.execute(
                "delete from lending.client_cif_review_confirmations where id = %s",
                (first["id"],),
            )
        assert _read(connection, first["id"]) == first


# Real-query acceptance reuses this file's loopback/disposable guard and rollback
# fixture. These schema fixtures do not stand in for office-role authorization.
def _seed_summary_case(connection: psycopg.Connection) -> dict[str, UUID]:
    case = _seed_case(connection)
    case["applicant"] = uuid4()
    connection.execute(
        """
        insert into lending.client_onboarding_applicants (
            id, application_reference, status, promoted_client_id,
            full_name, phone_number, email, present_address,
            national_id_egov_evidence_reference, national_id_status,
            tin_id_egov_evidence_reference, tin_id_status,
            meralco_bill_evidence_reference, meralco_bill_status,
            collector_visit_status, collector_visit_evidence_reference,
            eligibility_reviewed_by_user_id, eligibility_reviewed_at,
            privacy_consent, accuracy_declaration
        ) values (
            %s, %s, 'eligible_for_cif', %s,
            'Synthetic Intake Name', '00000000001', NULL, 'Synthetic intake address',
            'SYNTHETIC-NATIONAL', 'passed', 'SYNTHETIC-TIN', 'passed',
            'SYNTHETIC-RESIDENCE', 'passed', 'passed', 'SYNTHETIC-VISIT',
            %s, now(), true, true
        )
        """,
        (case["applicant"], f"SYN-REVIEW-{case['applicant'].hex}", case["client"], case["actor"]),
    )
    return case


def _summary_repository(connection: psycopg.Connection, monkeypatch):
    from contextlib import contextmanager

    from gilbic_backend import client_cif_repository as repository_module

    @contextmanager
    def test_connection():
        # Real PostgreSQL connection/SQL, only connection acquisition is redirected.
        # A savepoint preserves the surrounding fixture's final rollback.
        with connection.transaction():
            yield connection

    monkeypatch.setattr(repository_module, "open_connection", test_connection)
    return repository_module.PostgresClientCifRepository()


def _summary_state(connection: psycopg.Connection, case: dict[str, UUID]):
    return {
        "counts": _unrelated_counts(connection),
        "confirmations": connection.execute(
            "select * from lending.client_cif_review_confirmations order by id"
        ).fetchall(),
        "clients": connection.execute(
            "select * from lending.clients where id in (%s, %s) order by id",
            (case["client"], case["other"]),
        ).fetchall(),
        "versions": connection.execute(
            "select * from lending.client_cif_versions where client_id = %s order by id",
            (case["client"],),
        ).fetchall(),
        "applicant": connection.execute(
            "select * from lending.client_onboarding_applicants where id = %s",
            (case["applicant"],),
        ).fetchone(),
    }


@pytest.mark.parametrize(
    "cif_status,liveness",
    [("draft", "pending"), ("draft", "failed"), ("draft", "passed"), ("active", "passed")],
)
def test_summary_real_query_preserves_state_and_reads_cif_not_intake(
    connection, monkeypatch, cif_status, liveness
) -> None:
    case = _seed_summary_case(connection)
    connection.execute(
        """
        update lending.client_cif_versions
        set email = 'synthetic-cif@example.com', baseline_liveness_status = %s,
            baseline_face_scan_evidence_reference = %s
        where id = %s
        """,
        (liveness, None if liveness == "pending" else "SYNTHETIC-FACE", case["cif"]),
    )
    if cif_status == "active":
        connection.execute(
            """
            update lending.client_cif_versions
            set status = 'active', activated_at = now(),
                expires_at = now() + interval '5 years',
                review_due_at = now() + interval '5 years' - interval '90 days'
            where id = %s
            """,
            (case["cif"],),
        )
        connection.execute(
            "update lending.clients set status = 'active' where id = %s", (case["client"],)
        )
    repository = _summary_repository(connection, monkeypatch)
    before = _summary_state(connection, case)

    record = repository.get_review_summary(client_id=case["client"])
    repeated = repository.get_review_summary(client_id=case["client"])

    assert repeated == record
    assert record.id == case["cif"]
    assert record.client_id == case["client"]
    assert record.version_number == 1 and record.is_current is True
    assert record.status == cif_status
    assert record.baseline_liveness_status == liveness
    assert record.full_name == "Synthetic CIF Borrower"
    assert record.phone_number == "00000000000"
    assert record.email == "synthetic-cif@example.com"
    assert record.present_address == "Synthetic office test address"
    assert _summary_state(connection, case) == before


def test_summary_real_query_selects_current_version_and_preserves_old_evidence(
    connection, monkeypatch
) -> None:
    case = _seed_summary_case(connection)
    other_case = _seed_summary_case(connection)  # Same name, different stable identity.
    first = _insert(connection, case)
    connection.execute(
        "update lending.client_cif_versions set is_current = false, status = 'superseded' "
        "where id = %s",
        (case["cif"],),
    )
    connection.execute(
        "update lending.client_cif_versions set is_current = true, "
        "present_address = 'Synthetic revised CIF address' where id = %s",
        (case["next_cif"],),
    )
    repository = _summary_repository(connection, monkeypatch)
    before = _summary_state(connection, case)
    other_before = _summary_state(connection, other_case)

    record = repository.get_review_summary(client_id=case["client"])
    other_record = repository.get_review_summary(client_id=other_case["client"])

    assert record.id == case["next_cif"] and record.version_number == 2
    assert record.is_current is True and record.status == "draft"
    assert record.client_id == case["client"]
    assert record.present_address == "Synthetic revised CIF address"
    assert other_record.id == other_case["cif"]
    assert other_record.client_id == other_case["client"]
    assert _read(connection, first["id"]) == first
    assert _summary_state(connection, case) == before
    assert _summary_state(connection, other_case) == other_before


@pytest.mark.parametrize(
    "scenario",
    [
        "requirements_incomplete", "under_verification", "requirements_rejected",
        "wrong_link", "no_applicant", "no_current", "superseded",
        "blocked", "closed", "no_cif", "unknown_client",
    ],
)
def test_summary_real_query_rejects_unavailable_cif_without_writes(
    connection, monkeypatch, scenario
) -> None:
    from gilbic_backend.client_cif_repository import ClientCifConflict

    case = _seed_summary_case(connection)
    requested_client = case["client"]
    if scenario in {"requirements_incomplete", "under_verification", "requirements_rejected"}:
        connection.execute(
            "update lending.client_onboarding_applicants set status = %s where id = %s",
            (scenario, case["applicant"]),
        )
    elif scenario == "wrong_link":
        connection.execute(
            "update lending.client_onboarding_applicants set promoted_client_id = %s where id = %s",
            (case["other"], case["applicant"]),
        )
    elif scenario == "no_applicant":
        connection.execute(
            "delete from lending.client_onboarding_applicants where id = %s", (case["applicant"],)
        )
    elif scenario == "no_current":
        connection.execute(
            "update lending.client_cif_versions set is_current = false where id = %s",
            (case["cif"],),
        )
    elif scenario == "superseded":
        connection.execute(
            "update lending.client_cif_versions set status = 'superseded' where id = %s",
            (case["cif"],),
        )
    elif scenario in {"blocked", "closed"}:
        connection.execute(
            "update lending.clients set status = %s where id = %s", (scenario, case["client"])
        )
    elif scenario == "no_cif":
        connection.execute(
            "delete from lending.client_cif_versions where client_id = %s", (case["client"],)
        )
    elif scenario == "unknown_client":
        requested_client = uuid4()
    else:
        raise AssertionError(f"Unhandled synthetic scenario: {scenario}")
    repository = _summary_repository(connection, monkeypatch)
    before = _summary_state(connection, case)

    with pytest.raises(ClientCifConflict, match="No eligible current CIF is available"):
        repository.get_review_summary(client_id=requested_client)

    assert _summary_state(connection, case) == before


# Correction write-path proof uses real SQL and the same disposable database.
# API authorization remains covered separately; these are synthetic DB fixtures.
_CORRECTION_REASON = "Applicant corrected information during synthetic office review."
_INFORMATION_FIELDS = ("full_name", "phone_number", "email", "present_address")


def _correction_payload(connection, case):
    information = connection.execute(
        "select full_name, phone_number, email, present_address "
        "from lending.client_cif_versions where id = %s",
        (case["cif"],),
    ).fetchone()
    assert information is not None
    return {
        "actor_user_id": case["actor"],
        "client_id": case["client"],
        "cif_version_id": case["cif"],
        "expected_information": dict(information),
        "corrected_information": {**information, "phone_number": "09171111111"},
        "reason": _CORRECTION_REASON,
    }


def _assert_correction_state(connection, case, before, corrected, server_time):
    from copy import deepcopy

    expected = deepcopy(before)
    expected["counts"]["core.audit_logs"] += 1
    version = next(row for row in expected["versions"] if row["id"] == case["cif"])
    changed = [field for field in _INFORMATION_FIELDS if version[field] != corrected[field]]
    version.update(corrected)
    version["updated_at"] = server_time
    # Includes old CIF versions, confirmations, original intake, both Clients,
    # liveness/private references and counts of unrelated financial/Auth tables.
    assert _summary_state(connection, case) == expected
    audit = connection.execute(
        "select actor_user_id, action, target_type, target_id, details "
        "from core.audit_logs where target_id = %s "
        "and action = 'client_cif.draft_information_corrected'",
        (case["cif"],),
    ).fetchall()
    assert audit == [{
        "actor_user_id": case["actor"],
        "action": "client_cif.draft_information_corrected",
        "target_type": "client_cif_version",
        "target_id": case["cif"],
        "details": {
            "client_id": str(case["client"]),
            "changed_fields": changed,
            "reason": _CORRECTION_REASON,
        },
    }]


@pytest.mark.parametrize("field", [*_INFORMATION_FIELDS, "all"])
def test_correction_real_sql_updates_only_information_and_audit(
    connection, monkeypatch, field
) -> None:
    case = _seed_summary_case(connection)
    connection.execute(
        """
        update lending.client_cif_versions
        set email = 'synthetic-before@example.com', updated_at = '2000-01-01 00:00:00+00',
            national_id_egov_evidence_reference = 'SYNTHETIC-PRIVATE-NATIONAL',
            tin_id_egov_evidence_reference = 'SYNTHETIC-PRIVATE-TIN',
            meralco_bill_evidence_reference = 'SYNTHETIC-PRIVATE-RESIDENCE'
        where id = %s
        """,
        (case["cif"],),
    )
    other_case = _seed_summary_case(connection)  # Identical name must not select this CIF.
    payload = _correction_payload(connection, case)
    raw = {
        "full_name": "  Synthetic   Corrected Borrower ",
        "phone_number": "0917-111-1111",
        "email": " UPDATED@EXAMPLE.COM ",
        "present_address": " Synthetic   corrected office address ",
    }
    normalized = {
        "full_name": "Synthetic Corrected Borrower",
        "phone_number": "09171111111",
        "email": "updated@example.com",
        "present_address": "Synthetic corrected office address",
    }
    changed_fields = _INFORMATION_FIELDS if field == "all" else (field,)
    # A blank optional email explicitly clears it; the all-fields case sets one.
    if field == "email":
        raw[field], normalized[field] = "   ", None
    payload["corrected_information"] = {
        **payload["expected_information"], **{key: raw[key] for key in changed_fields},
    }
    corrected = {
        **payload["expected_information"], **{key: normalized[key] for key in changed_fields},
    }
    repository = _summary_repository(connection, monkeypatch)
    before = _summary_state(connection, case)
    other_before = _summary_state(connection, other_case)
    server_time = connection.execute("select now() as value").fetchone()["value"]

    record = repository.correct_draft_information(**payload)

    assert record.id == case["cif"] and record.client_id == case["client"]
    assert {key: getattr(record, key) for key in _INFORMATION_FIELDS} == corrected
    _assert_correction_state(connection, case, before, corrected, server_time)
    other_before["counts"]["core.audit_logs"] += 1
    assert _summary_state(connection, other_case) == other_before


@pytest.mark.parametrize("field", _INFORMATION_FIELDS)
def test_correction_real_sql_rejects_stale_review_without_writes(
    connection, monkeypatch, field
) -> None:
    from gilbic_backend.client_cif_repository import ClientCifConflict

    case = _seed_summary_case(connection)
    payload = _correction_payload(connection, case)
    payload["expected_information"][field] = "Obsolete reviewed value"
    repository = _summary_repository(connection, monkeypatch)
    before = _summary_state(connection, case)
    with pytest.raises(ClientCifConflict, match="refresh the office review"):
        repository.correct_draft_information(**payload)
    assert _summary_state(connection, case) == before


@pytest.mark.parametrize("scenario", [
    "confirmed", "active", "superseded", "noncurrent", "wrong_version", "wrong_client",
    "blocked", "closed", "requirements_incomplete", "under_verification",
    "requirements_rejected", "wrong_link",
])
def test_correction_real_sql_rejects_ineligible_or_confirmed_target(
    connection, monkeypatch, scenario
) -> None:
    from gilbic_backend.client_cif_repository import ClientCifConflict

    case = _seed_summary_case(connection)
    payload = _correction_payload(connection, case)
    if scenario == "confirmed":
        _insert(connection, case)
    elif scenario == "active":
        connection.execute(
            """
            update lending.client_cif_versions set status = 'active',
                baseline_liveness_status = 'passed',
                baseline_face_scan_evidence_reference = 'SYNTHETIC-FACE',
                activated_at = now(), expires_at = now() + interval '5 years',
                review_due_at = now() + interval '5 years' - interval '90 days'
            where id = %s
            """,
            (case["cif"],),
        )
        connection.execute(
            "update lending.clients set status = 'active' where id = %s", (case["client"],)
        )
    elif scenario == "superseded":
        connection.execute(
            "update lending.client_cif_versions set status = 'superseded' where id = %s",
            (case["cif"],),
        )
    elif scenario == "noncurrent":
        connection.execute(
            "update lending.client_cif_versions set is_current = false where id = %s",
            (case["cif"],),
        )
    elif scenario == "wrong_version":
        payload["cif_version_id"] = case["next_cif"]
    elif scenario == "wrong_client":
        payload["client_id"] = case["other"]
    elif scenario in {"blocked", "closed"}:
        connection.execute(
            "update lending.clients set status = %s where id = %s", (scenario, case["client"])
        )
    elif scenario in {"requirements_incomplete", "under_verification", "requirements_rejected"}:
        connection.execute(
            "update lending.client_onboarding_applicants set status = %s where id = %s",
            (scenario, case["applicant"]),
        )
    elif scenario == "wrong_link":
        connection.execute(
            "update lending.client_onboarding_applicants set promoted_client_id = %s where id = %s",
            (case["other"], case["applicant"]),
        )
    else:
        raise AssertionError(scenario)
    repository = _summary_repository(connection, monkeypatch)
    before = _summary_state(connection, case)
    with pytest.raises(ClientCifConflict):
        repository.correct_draft_information(**payload)
    assert _summary_state(connection, case) == before


def test_correction_real_sql_normalized_noop_preserves_timestamp_and_audit(
    connection, monkeypatch
) -> None:
    case = _seed_summary_case(connection)
    payload = _correction_payload(connection, case)
    payload["corrected_information"] = {
        **payload["expected_information"], "full_name": "  Synthetic   CIF Borrower  ",
    }
    repository = _summary_repository(connection, monkeypatch)
    before = _summary_state(connection, case)
    record = repository.correct_draft_information(**payload)
    assert record.id == case["cif"] and record.status == "draft"
    assert _summary_state(connection, case) == before


def test_correction_real_sql_audit_failure_rolls_back_information(connection, monkeypatch) -> None:
    case = _seed_summary_case(connection)
    payload = _correction_payload(connection, case)
    repository = _summary_repository(connection, monkeypatch)
    # Added only inside the rollback-isolated fixture. Never disable an existing guard.
    name = f"cif_audit_failure_{case['cif'].hex}"
    connection.execute(sql.SQL(
        "create function pg_temp.{}() returns trigger language plpgsql as $$ "
        "begin raise exception 'SYNTHETIC CIF correction audit failure' "
        "using errcode = '23514'; end; $$"
    ).format(sql.Identifier(name)))
    connection.execute(sql.SQL(
        "create trigger {} before insert on core.audit_logs for each row "
        "when (NEW.action = 'client_cif.draft_information_corrected' "
        "and NEW.target_id = {}::uuid) execute function pg_temp.{}()"
    ).format(sql.Identifier(name), sql.Literal(str(case["cif"])), sql.Identifier(name)))
    before = _summary_state(connection, case)
    with pytest.raises(psycopg.errors.CheckViolation, match="SYNTHETIC CIF correction audit failure"):
        repository.correct_draft_information(**payload)
    assert _summary_state(connection, case) == before


@pytest.mark.parametrize("winner", ["correction", "confirmation"])
def test_correction_real_sql_waits_for_lock_and_rechecks_committed_state(
    runtime_url, monkeypatch, winner
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from contextlib import contextmanager
    from queue import Queue
    from threading import Event, get_ident
    from time import monotonic

    from gilbic_backend import client_cif_repository as module

    # Intentional committed synthetic rows, like the migration-rerun proof above:
    # only this module's guarded, disposable database is used and later dropped.
    options = "-c lock_timeout=10000 -c statement_timeout=15000"
    with psycopg.connect(runtime_url, autocommit=True, row_factory=dict_row) as observer:
        with observer.transaction():
            case = _seed_summary_case(observer)
        payload = _correction_payload(observer, case)
        before = _summary_state(observer, case)
        owner = psycopg.connect(runtime_url, row_factory=dict_row, options=options, connect_timeout=5)
        owner_thread = get_ident()
        contender_pid = Queue()

        @contextmanager
        def actual_transaction():
            if get_ident() == owner_thread:
                with owner.transaction():
                    yield owner
            else:
                with psycopg.connect(
                    runtime_url, row_factory=dict_row, options=options, connect_timeout=5
                ) as contender:
                    contender_pid.put(contender.info.backend_pid)
                    yield contender

        monkeypatch.setattr(module, "open_connection", actual_transaction)
        repository = module.PostgresClientCifRepository()
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            owner.execute(
                "select cif.id from lending.client_cif_versions cif "
                "join lending.client_onboarding_applicants applicant "
                "on applicant.promoted_client_id = cif.client_id "
                "join lending.clients client on client.id = cif.client_id "
                "where cif.id = %s for update of cif, applicant, client",
                (case["cif"],),
            )
            server_time = owner.execute("select now() as value").fetchone()["value"]
            waiting_payload = {
                **payload,
                "corrected_information": {**payload["expected_information"], "phone_number": "09172222222"},
            }
            future = executor.submit(repository.correct_draft_information, **waiting_payload)
            pid = contender_pid.get(timeout=5)
            deadline = monotonic() + 5
            while True:
                blockers = observer.execute(
                    "select pg_blocking_pids(%s) as blockers", (pid,)
                ).fetchone()["blockers"]
                if owner.info.backend_pid in blockers:
                    break
                assert monotonic() < deadline, "Correction did not wait on the held CIF lock"
                Event().wait(0.02)
            if winner == "correction":
                repository.correct_draft_information(**payload)
                message = "refresh the office review"
            else:
                # Schema-level fixture only, not the unfinished confirmation API.
                confirmation = _insert(owner, case)
                message = "new review/version cycle"
            owner.commit()
            with pytest.raises(module.ClientCifConflict, match=message):
                future.result(timeout=15)
            if winner == "correction":
                _assert_correction_state(
                    observer, case, before, payload["corrected_information"], server_time
                )
            else:
                before["confirmations"] = sorted(
                    [*before["confirmations"], confirmation], key=lambda row: row["id"]
                )
                assert _summary_state(observer, case) == before
        finally:
            # Unblock the worker even if an assertion fails; SQL timeouts bound shutdown.
            owner.rollback()
            executor.shutdown(wait=True, cancel_futures=True)
            owner.close()
