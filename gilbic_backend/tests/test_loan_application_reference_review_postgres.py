"""Protected exact-reference reads over real immutable application history."""
from __future__ import annotations

from uuid import uuid4

import psycopg
import pytest

from gilbic_backend.loan_application_information import LoanApplicationInformation
from gilbic_backend.loan_application_repository import LoanApplicationAccessDenied
from test_loan_application_repository_postgres import (
    DATABASE_URL,
    _append,
    _create,
    _read_version,
    _repository,
    _seed,
    _state,
    connection as connection,
    runtime_url as runtime_url,
)


pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="GILBIC_TEST_DATABASE_URL is not configured",
)


def _review(repository, case, reference, **changes):
    return repository.get_latest_by_reference(
        **{
            "actor_user_id": case["actor"],
            "client_id": case["client"],
            "application_reference": reference,
            **changes,
        }
    )


@pytest.mark.parametrize("role", ["employee", "management"])
def test_latest_version_is_scoped_to_exact_application_and_is_read_only(
    connection, monkeypatch, role,
):
    repository = _repository(connection, monkeypatch)
    case = _seed(connection, role)
    reference = f"Office/  MiXeD {uuid4().hex}"
    first = _create(repository, case, reference)
    latest = _append(repository, case, first)
    other = _create(repository, case, f"OTHER-{uuid4().hex}")
    _append(repository, case, other)
    _append(
        repository, case, other, expected_version_number=2,
        information=LoanApplicationInformation(request={"requested_amount": "7000.00"}),
    )
    before = _state(connection, case)
    statements = []

    class RecordingCursor(psycopg.Cursor):
        def execute(self, query, params=None, **kwargs):
            statements.append((" ".join(query.lower().split()), params))
            return super().execute(query, params, **kwargs)

    original_factory = connection.cursor_factory
    connection.cursor_factory = RecordingCursor
    try:
        record = _review(repository, case, f" \t{reference}\r\n")
    finally:
        connection.cursor_factory = original_factory

    assert record.id == latest.id and record.application_id == first.application_id
    assert record.version_number == 2
    assert record.application_reference == reference
    assert record.client_id == case["client"] and record.cif_version_id == case["cif"]
    assert record.cif_version_number == 1
    assert record.information == latest.information
    assert record.requested_loan_type_name is None
    assert len(statements) == 2  # Persisted actor check and one selected-version read.
    for query, _ in statements:
        assert query.startswith("select ")
        assert "for update" not in query and "for share" not in query
    assert statements[-1][1] == (case["client"], reference)
    assert _state(connection, case) == before
    assert _read_version(repository, case, first) == first
    assert not hasattr(first, "cif_version_number")


def test_reference_matching_is_case_sensitive_without_internal_normalization(
    connection, monkeypatch,
):
    repository = _repository(connection, monkeypatch)
    case = _seed(connection)
    reference = f"Office/  MiXeD {uuid4().hex}" + "-Long" * 80
    first = _create(repository, case, reference)
    other = _create(repository, case, reference.lower())
    before = _state(connection, case)

    assert _review(repository, case, reference).id == first.id
    assert _review(repository, case, reference.lower()).id == other.id
    assert _review(repository, case, " ".join(reference.split())) is None
    assert _state(connection, case) == before


@pytest.mark.parametrize("candidate", ["unknown", "partial", "wildcard", "sql", "name"])
def test_unmatched_reference_never_searches_or_falls_back(connection, monkeypatch, candidate):
    repository = _repository(connection, monkeypatch)
    case = _seed(connection)
    reference = f"Office-{uuid4().hex}"
    _create(repository, case, reference)
    before = _state(connection, case)
    entered = {
        "unknown": f"Unknown-{uuid4().hex}",
        "partial": reference[:-1],
        "wildcard": reference[:-1] + "%",
        "sql": reference + "' OR 1=1 --",
        "name": "Synthetic CIF Borrower",
    }[candidate]

    assert _review(repository, case, entered) is None
    assert _state(connection, case) == before


def test_exact_reference_cannot_select_another_client_application(connection, monkeypatch):
    repository = _repository(connection, monkeypatch)
    case, other = _seed(connection), _seed(connection)
    reference = f"Office-{uuid4().hex}"
    _create(repository, other, reference)
    before = _state(connection, case)

    assert _review(repository, case, reference) is None
    assert _state(connection, case) == before


@pytest.mark.parametrize("client_status", ["inactive", "blocked", "closed"])
def test_historical_review_keeps_exact_attached_cif_after_source_supersession(
    connection, monkeypatch, client_status,
):
    repository = _repository(connection, monkeypatch)
    case = _seed(connection)
    reference = f"Office-{uuid4().hex}"
    first = _create(repository, case, reference)
    connection.execute(
        "update lending.client_cif_versions set is_current = false, status = 'superseded' "
        "where id = %s", (case["cif"],),
    )
    connection.execute(
        "update lending.client_cif_versions set is_current = true where id = %s",
        (case["next_cif"],),
    )
    connection.execute(
        "update lending.clients set status = %s where id = %s",
        (client_status, case["client"]),
    )
    connection.execute(
        "update lending.client_onboarding_applicants set status = 'under_verification' "
        "where id = %s", (case["applicant"],),
    )
    before = _state(connection, case)

    record = _review(repository, case, reference)

    assert record.id == first.id
    assert record.cif_version_id == case["cif"]
    assert record.cif_version_number == 1
    assert _state(connection, case) == before


@pytest.mark.parametrize("requested_type", [None, "unknown"])
def test_absent_catalog_entry_does_not_hide_saved_application(
    connection, monkeypatch, requested_type,
):
    repository = _repository(connection, monkeypatch)
    case = _seed(connection)
    reference = f"Office-{uuid4().hex}"
    information = LoanApplicationInformation(request={
        "requested_loan_type_id": uuid4() if requested_type else None,
        "requested_amount": "9007199254740993.01",
    })
    first = _create(repository, case, reference, information=information)
    before = _state(connection, case)

    record = _review(repository, case, reference)

    assert record.id == first.id
    assert record.information == first.information
    assert record.requested_loan_type_name is None
    assert _state(connection, case) == before


def test_catalog_label_is_current_metadata_and_does_not_rewrite_saved_information(
    connection, monkeypatch,
):
    repository = _repository(connection, monkeypatch)
    case = _seed(connection)
    loan_type_id = uuid4()
    connection.execute(
        "insert into lending.loan_types (id, code, name, term_days, calculation_mode, is_active) "
        "values (%s, %s, 'Synthetic Original Label', 60, 'custom', false)",
        (loan_type_id, f"SYN-TYPE-{loan_type_id.hex}"),
    )
    reference = f"Office-{uuid4().hex}"
    first = _create(repository, case, reference, information=LoanApplicationInformation(
        request={"requested_loan_type_id": loan_type_id},
    ))
    assert _review(repository, case, reference).requested_loan_type_name == "Synthetic Original Label"
    connection.execute(
        "update lending.loan_types set name = 'Synthetic Current Label' where id = %s",
        (loan_type_id,),
    )
    before = _state(connection, case)

    record = _review(repository, case, reference)

    assert record.requested_loan_type_name == "Synthetic Current Label"
    assert record.information == first.information
    assert _read_version(repository, case, first) == first
    assert _state(connection, case) == before


@pytest.mark.parametrize("denial", ["collector", "inactive", "no_permission"])
def test_reference_reader_requires_persisted_office_authority(connection, monkeypatch, denial):
    repository = _repository(connection, monkeypatch)
    case = _seed(connection)
    reference = f"Office-{uuid4().hex}"
    _create(repository, case, reference)
    if denial == "collector":
        other = _seed(connection, "collector")
        actor_id = other["actor"]
    else:
        actor_id = case["actor"]
        if denial == "inactive":
            connection.execute("update core.users set status = 'inactive' where id = %s", (actor_id,))
        else:
            connection.execute(
                "delete from core.role_permissions where permission_code = %s",
                ("client_onboarding.requirement.review",),
            )
    before = _state(connection, case)

    with pytest.raises(LoanApplicationAccessDenied):
        _review(repository, case, reference, actor_user_id=actor_id)
    assert _state(connection, case) == before
