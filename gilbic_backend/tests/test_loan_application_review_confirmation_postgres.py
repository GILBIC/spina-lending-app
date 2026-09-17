"""Real application-review confirmation proof on the guarded disposable database.

This confirms only the applicant's review of saved CIF/application information.
It does not approve a loan, sign a contract, release cash, create credentials,
or start a schedule.
"""
from __future__ import annotations

from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from gilbic_backend.loan_application_information import LoanApplicationInformation
from test_client_cif_review_confirmation_postgres import (
    DATABASE_URL,
    _insert as _insert_cif_confirmation,
    _seed_case as _seed_cif_case,
    connection as connection,
    runtime_url as runtime_url,
)
from test_loan_application_repository_postgres import (
    PERMISSION,
    _append,
    _create,
    _repository,
    _seed,
)


pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="GILBIC_TEST_DATABASE_URL is not configured"
)
TABLE = "loan_application_review_confirmations"
MODULE = "gilbic_backend.loan_application_repository"
MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0121_add_loan_application_review_confirmation.sql"
)
SYNTHETIC_LOAN_TYPE_ID = UUID("00000000-0000-0000-0000-0000000000a1")


@pytest.fixture(autouse=True)
def require_confirmation_schema(connection) -> None:
    row = connection.execute(
        "select to_regclass('lending.loan_application_review_confirmations') "
        "as relation"
    ).fetchone()
    assert row["relation"] is not None, (
        "Loan application review confirmation schema is not implemented"
    )


def _module():
    return import_module(MODULE)


def _complete_information(
    amount: str = "3000.00",
    *,
    purpose: str = "Synthetic working-capital request",
) -> LoanApplicationInformation:
    return LoanApplicationInformation(
        request={
            "requested_loan_type_id": SYNTHETIC_LOAN_TYPE_ID,
            "purpose": purpose,
            "requested_amount": amount,
            "requested_payment_arrangement": "Daily office collection",
            "requested_term": "60 calendar days",
        },
        repayment={
            "repayment_source": "Synthetic microbusiness",
            "source_details": "Synthetic sari-sari income declaration",
            "monthly_gross_income": "12000.00",
            "monthly_net_income": "8000.00",
            "has_existing_obligations": False,
        },
    )


def _incomplete_information(section: str) -> LoanApplicationInformation:
    complete = _complete_information()
    payload = complete.model_dump(mode="json")
    if section == "request":
        payload["request"]["purpose"] = None
    elif section == "repayment":
        payload["repayment"]["repayment_source"] = None
    else:
        raise AssertionError(f"Unhandled section: {section}")
    return LoanApplicationInformation.model_validate(payload)


def _confirm(
    repository,
    case,
    version,
    evidence: str = "SYNTHETIC-APPLICATION-CONFIRMATION",
    **changes: Any,
):
    values = {
        "actor_user_id": case["actor"],
        "client_id": case["client"],
        "application_id": version.application_id,
        "application_version_id": version.id,
        "applicant_confirmation_evidence_reference": evidence,
    }
    values.update(changes)
    method = getattr(repository, "confirm_review", None)
    if method is None:
        pytest.fail("Application review confirmation repository is not implemented")
    return method(**values)


def _insert_direct(connection, version, actor_user_id, **overrides: Any):
    values = {
        "application_version_id": version.id,
        "application_id": version.application_id,
        "client_id": version.client_id,
        "cif_version_id": version.cif_version_id,
        "applicant_confirmation_evidence_reference": (
            "SYNTHETIC-APPLICATION-CONFIRMATION"
        ),
        "witnessed_by_user_id": actor_user_id,
    }
    values.update(overrides)
    return connection.execute(
        """
        insert into lending.loan_application_review_confirmations (
            application_version_id,
            application_id,
            client_id,
            cif_version_id,
            applicant_confirmation_evidence_reference,
            witnessed_by_user_id
        ) values (
            %(application_version_id)s,
            %(application_id)s,
            %(client_id)s,
            %(cif_version_id)s,
            %(applicant_confirmation_evidence_reference)s,
            %(witnessed_by_user_id)s
        )
        returning *
        """,
        values,
    ).fetchone()


def _read(connection, confirmation_id):
    return connection.execute(
        "select * from lending.loan_application_review_confirmations where id = %s",
        (confirmation_id,),
    ).fetchone()


def _confirmation_rows(connection, application_id):
    return connection.execute(
        """
        select *
        from lending.loan_application_review_confirmations
        where application_id = %s
        order by confirmed_at, id
        """,
        (application_id,),
    ).fetchall()


def _unrelated_counts(connection):
    tables = connection.execute(
        """
        select schemaname, tablename
        from pg_tables
        where schemaname in ('core', 'lending', 'accounting', 'mobile', 'auth')
          and not (
              schemaname = 'lending'
              and tablename = 'loan_application_review_confirmations'
          )
        order by schemaname, tablename
        """
    ).fetchall()
    return {
        f"{table['schemaname']}.{table['tablename']}": connection.execute(
            sql.SQL("select count(*) as count from {}.{}").format(
                sql.Identifier(table["schemaname"]),
                sql.Identifier(table["tablename"]),
            )
        ).fetchone()["count"]
        for table in tables
    }


def _seed_confirmable(connection, monkeypatch, role: str = "employee"):
    repository = _repository(connection, monkeypatch)
    case = _seed(connection, role)
    _insert_cif_confirmation(
        connection,
        case,
        review_snapshot=Jsonb(
            {
                "full_name": "Synthetic CIF Borrower",
                "phone_number": "00000000000",
                "email": None,
                "present_address": "Synthetic office test address",
            }
        ),
    )
    information = _complete_information()
    version = _create(
        repository,
        case,
        f"SYN-APP-{uuid4().hex}",
        information=information,
    )
    assert version.information.missing_fields() == ()
    return repository, case, version


@pytest.mark.parametrize("role", ["employee", "management"])
def test_confirmation_binds_exact_saved_version_and_server_witness_time(
    connection, monkeypatch, role
) -> None:
    repository, case, version = _seed_confirmable(
        connection, monkeypatch, role
    )
    before = _unrelated_counts(connection)

    confirmation = _confirm(repository, case, version)

    stored = _read(connection, confirmation.id)
    assert stored is not None
    assert confirmation.application_version_id == stored["application_version_id"]
    assert confirmation.application_version_id == version.id
    assert confirmation.application_id == stored["application_id"]
    assert confirmation.application_id == version.application_id
    assert confirmation.client_id == stored["client_id"] == case["client"]
    assert confirmation.cif_version_id == stored["cif_version_id"] == case["cif"]
    assert (
        confirmation.applicant_confirmation_evidence_reference
        == stored["applicant_confirmation_evidence_reference"]
        == "SYNTHETIC-APPLICATION-CONFIRMATION"
    )
    assert (
        confirmation.witnessed_by_user_id
        == stored["witnessed_by_user_id"]
        == case["actor"]
    )
    server_now = connection.execute("select now() as now").fetchone()["now"]
    assert confirmation.confirmed_at == stored["confirmed_at"] == server_now
    assert _unrelated_counts(connection) == before


@pytest.mark.parametrize("section", ["request", "repayment"])
def test_incomplete_application_information_cannot_be_confirmed(
    connection, monkeypatch, section
) -> None:
    repository = _repository(connection, monkeypatch)
    case = _seed(connection)
    _insert_cif_confirmation(connection, case)
    version = _create(
        repository,
        case,
        f"SYN-APP-{uuid4().hex}",
        information=_incomplete_information(section),
    )
    assert version.information.missing_fields()
    before = _confirmation_rows(connection, version.application_id)

    with pytest.raises(
        _module().LoanApplicationConflict,
        match="Application information is incomplete",
    ):
        _confirm(repository, case, version)

    assert _confirmation_rows(connection, version.application_id) == before


def test_application_confirmation_requires_existing_exact_cif_review(
    connection, monkeypatch
) -> None:
    repository = _repository(connection, monkeypatch)
    case = _seed(connection)
    version = _create(
        repository,
        case,
        f"SYN-APP-{uuid4().hex}",
        information=_complete_information(),
    )

    with pytest.raises(
        _module().LoanApplicationConflict,
        match="CIF review confirmation is required",
    ):
        _confirm(repository, case, version)
    assert _confirmation_rows(connection, version.application_id) == []


@pytest.mark.parametrize("source_state", ["superseded_cif", "blocked_client"])
def test_new_confirmation_rejects_stale_or_ineligible_source_state(
    connection, monkeypatch, source_state
) -> None:
    repository, case, version = _seed_confirmable(connection, monkeypatch)
    if source_state == "superseded_cif":
        connection.execute(
            """
            update lending.client_cif_versions
            set is_current = false, status = 'superseded'
            where id = %s
            """,
            (case["cif"],),
        )
        connection.execute(
            "update lending.client_cif_versions set is_current = true where id = %s",
            (case["next_cif"],),
        )
    else:
        connection.execute(
            "update lending.clients set status = 'blocked' where id = %s",
            (case["client"],),
        )

    with pytest.raises(
        _module().LoanApplicationConflict,
        match="eligible current CIF",
    ):
        _confirm(repository, case, version)
    assert _confirmation_rows(connection, version.application_id) == []


def test_stale_application_version_cannot_be_newly_confirmed(
    connection, monkeypatch
) -> None:
    repository, case, first = _seed_confirmable(connection, monkeypatch)
    second = _append(
        repository,
        case,
        first,
        information=_complete_information(
            "5000.00", purpose="Synthetic corrected working-capital request"
        ),
    )
    assert second.version_number == 2

    with pytest.raises(
        _module().LoanApplicationConflict,
        match="latest application version",
    ):
        _confirm(repository, case, first)
    assert _confirmation_rows(connection, first.application_id) == []


def test_post_confirmation_correction_uses_new_version_and_new_confirmation(
    connection, monkeypatch
) -> None:
    repository, case, first = _seed_confirmable(connection, monkeypatch)
    first_confirmation = _confirm(repository, case, first, "SYNTHETIC-ACK-V1")
    original_confirmation = _read(connection, first_confirmation.id)
    second = _append(
        repository,
        case,
        first,
        information=_complete_information(
            "5000.00", purpose="Synthetic corrected request after review"
        ),
    )
    second_confirmation = _confirm(repository, case, second, "SYNTHETIC-ACK-V2")

    assert second.version_number == 2
    assert first.id != second.id
    assert first_confirmation.id != second_confirmation.id
    rows = _confirmation_rows(connection, first.application_id)
    # Both writes share this transaction's now(); UUID order is not version order.
    assert len(rows) == 2
    assert {
        row["application_version_id"]: row["applicant_confirmation_evidence_reference"]
        for row in rows
    } == {
        first.id: "SYNTHETIC-ACK-V1",
        second.id: "SYNTHETIC-ACK-V2",
    }
    assert _read(connection, first_confirmation.id) == original_confirmation


def test_identical_confirmation_retry_returns_original_without_duplicate(
    connection, monkeypatch
) -> None:
    repository, case, version = _seed_confirmable(connection, monkeypatch)
    first = _confirm(repository, case, version)
    before = _confirmation_rows(connection, version.application_id)

    assert _confirm(repository, case, version) == first
    assert _confirmation_rows(connection, version.application_id) == before


@pytest.mark.parametrize("conflict", ["evidence", "witness"])
def test_conflicting_confirmation_retry_never_rewrites_evidence(
    connection, monkeypatch, conflict
) -> None:
    repository, case, version = _seed_confirmable(connection, monkeypatch)
    first = _confirm(repository, case, version)
    changes: dict[str, Any] = {}
    if conflict == "evidence":
        changes["evidence"] = "SYNTHETIC-DIFFERENT-ACK"
    else:
        other = _seed(connection, "management")
        changes["actor_user_id"] = other["actor"]
    before = _confirmation_rows(connection, version.application_id)

    with pytest.raises(
        _module().LoanApplicationConflict,
        match="already confirmed with different evidence",
    ):
        if conflict == "evidence":
            _confirm(
                repository,
                case,
                version,
                evidence=changes["evidence"],
            )
        else:
            _confirm(
                repository,
                case,
                version,
                actor_user_id=changes["actor_user_id"],
            )

    assert _read(connection, first.id)["id"] == first.id
    assert _confirmation_rows(connection, version.application_id) == before


def test_collector_cannot_confirm_even_when_permission_is_granted(
    connection, monkeypatch
) -> None:
    repository, case, version = _seed_confirmable(connection, monkeypatch)
    collector = _seed(connection, "collector")

    with pytest.raises(_module().LoanApplicationAccessDenied):
        _confirm(
            repository,
            case,
            version,
            actor_user_id=collector["actor"],
        )
    assert _confirmation_rows(connection, version.application_id) == []


def test_confirmation_rechecks_permission_at_confirmation_time(
    connection, monkeypatch
) -> None:
    repository, case, version = _seed_confirmable(connection, monkeypatch)
    connection.execute(
        """
        delete from core.role_permissions
        where permission_code = %s
          and role_id in (
              select role_id from core.user_roles where user_id = %s
          )
        """,
        (PERMISSION, case["actor"]),
    )

    with pytest.raises(_module().LoanApplicationAccessDenied):
        _confirm(repository, case, version)
    assert _confirmation_rows(connection, version.application_id) == []


@pytest.mark.parametrize("field", ["application_id", "client_id", "cif_version_id"])
def test_schema_rejects_cross_record_binding(
    connection, monkeypatch, field
) -> None:
    _, case, version = _seed_confirmable(connection, monkeypatch)
    _, other, other_version = _seed_confirmable(
        connection, monkeypatch, "management"
    )
    values = {
        "application_id": other_version.application_id,
        "client_id": other["client"],
        "cif_version_id": case["next_cif"],
    }

    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with connection.transaction():
            _insert_direct(
                connection,
                version,
                case["actor"],
                **{field: values[field]},
            )


@pytest.mark.parametrize(
    "field,value,sqlstate",
    [
        ("application_version_id", None, "23502"),
        ("application_id", None, "23502"),
        ("client_id", None, "23502"),
        ("cif_version_id", None, "23502"),
        ("applicant_confirmation_evidence_reference", None, "23502"),
        ("applicant_confirmation_evidence_reference", "", "23514"),
        ("applicant_confirmation_evidence_reference", "   ", "23514"),
        ("witnessed_by_user_id", None, "23502"),
        ("witnessed_by_user_id", uuid4(), "23503"),
    ],
)
def test_schema_rejects_invalid_confirmation_metadata(
    connection, monkeypatch, field, value, sqlstate
) -> None:
    _, case, version = _seed_confirmable(connection, monkeypatch)

    with pytest.raises(psycopg.IntegrityError) as rejected:
        with connection.transaction():
            _insert_direct(
                connection,
                version,
                case["actor"],
                **{field: value},
            )
    assert rejected.value.sqlstate == sqlstate


@pytest.mark.parametrize("operation", ["update", "delete", "truncate"])
def test_confirmation_history_is_immutable(
    connection, monkeypatch, operation
) -> None:
    repository, case, version = _seed_confirmable(connection, monkeypatch)
    confirmation = _confirm(repository, case, version)
    statements = {
        "update": (
            """
            update lending.loan_application_review_confirmations
            set applicant_confirmation_evidence_reference = 'TAMPERED'
            where id = %s
            """,
            (confirmation.id,),
        ),
        "delete": (
            "delete from lending.loan_application_review_confirmations where id = %s",
            (confirmation.id,),
        ),
        "truncate": (
            "truncate lending.loan_application_review_confirmations",
            None,
        ),
    }
    statement, params = statements[operation]

    with pytest.raises(
        psycopg.errors.CheckViolation,
        match="Loan application history is immutable",
    ):
        with connection.transaction():
            connection.execute(statement, params)
    assert _read(connection, confirmation.id)["id"] == confirmation.id


def _direct_application_version(connection, case):
    application_id = uuid4()
    version_id = uuid4()
    connection.execute(
        """
        insert into lending.loan_applications (
            id, application_reference, client_id, created_by_user_id
        ) values (%s, %s, %s, %s)
        """,
        (
            application_id,
            f"SYN-RERUN-{application_id.hex}",
            case["client"],
            case["actor"],
        ),
    )
    connection.execute(
        """
        insert into lending.loan_application_versions (
            id, application_id, client_id, cif_version_id,
            version_number, information, recorded_by_user_id
        ) values (%s, %s, %s, %s, 1, %s, %s)
        """,
        (
            version_id,
            application_id,
            case["client"],
            case["cif"],
            Jsonb({"request": {}, "repayment": {}}),
            case["actor"],
        ),
    )

    return SimpleNamespace(
        id=version_id,
        application_id=application_id,
        client_id=case["client"],
        cif_version_id=case["cif"],
    )


def test_migration_rerun_preserves_confirmation_and_guards(runtime_url) -> None:
    with psycopg.connect(
        runtime_url, autocommit=True, row_factory=dict_row
    ) as connection:
        case = _seed_cif_case(connection)
        version = _direct_application_version(connection, case)
        first = _insert_direct(connection, version, case["actor"])
        migration_sql = MIGRATION.read_text(encoding="utf-8")

        for _ in range(2):
            connection.execute(migration_sql)
            assert _read(connection, first["id"]) == first

        with pytest.raises(
            psycopg.errors.CheckViolation,
            match="Loan application history is immutable",
        ):
            connection.execute(
                "delete from lending.loan_application_review_confirmations "
                "where id = %s",
                (first["id"],),
            )
        assert _read(connection, first["id"]) == first
