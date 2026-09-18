"""Real PostgreSQL proof for office intake reference to stable Client selection.

Reuse the guarded disposable onboarding database and rollback fixtures. Only
connection acquisition is redirected; SQL, joins, constraints and rows are real.
HTTP authorization and the separate current-CIF review remain later boundaries.
"""
from __future__ import annotations

from contextlib import contextmanager
from importlib import import_module
from uuid import uuid4

import pytest
from psycopg.rows import tuple_row

from test_client_cif_review_confirmation_postgres import (
    DATABASE_URL,
    _insert,
    _read,
    _seed_summary_case,
    _summary_state,
    connection as connection,
    runtime_url as runtime_url,
)


pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="GILBIC_TEST_DATABASE_URL is not configured"
)
MODULE = "gilbic_backend.client_onboarding_repository"


def _repository(connection, monkeypatch):
    module = import_module(MODULE)

    @contextmanager
    def acquire():
        # Preserve the fixture's outer rollback while executing the real query.
        # Match open_connection's default rows; state helpers keep dict rows.
        previous_row_factory = connection.row_factory
        connection.row_factory = tuple_row
        try:
            with connection.transaction():
                yield connection
        finally:
            connection.row_factory = previous_row_factory

    monkeypatch.setattr(module, "open_connection", acquire)
    return module.PostgresClientOnboardingRepository()


def _method(repository):
    method = getattr(repository, "find_cif_client_by_reference", None)
    if method is None:
        pytest.fail("Office CIF Client selection is not implemented", pytrace=False)
    return method


def _reference(connection, case):
    return connection.execute(
        "select application_reference from lending.client_onboarding_applicants "
        "where id = %s",
        (case["applicant"],),
    ).fetchone()["application_reference"]


def _assert_selection(record, case, reference):
    record_type = import_module(MODULE).ClientOnboardingRecord
    assert isinstance(record, record_type)
    assert record == record_type(
        application_reference=reference,
        status="eligible_for_cif",
        promoted_client_id=case["client"],
    )


@pytest.mark.parametrize("client_status", ["inactive", "active"])
def test_eligible_office_reference_returns_existing_stable_client(
    connection, monkeypatch, client_status
):
    case = _seed_summary_case(connection)
    connection.execute(
        "update lending.clients set status = %s where id = %s",
        (client_status, case["client"]),
    )
    reference = _reference(connection, case)
    repository = _repository(connection, monkeypatch)
    before = _summary_state(connection, case)

    record = _method(repository)(application_reference=reference)

    _assert_selection(record, case, reference)
    assert _summary_state(connection, case) == before


def test_case_insensitive_exact_lookup_trims_only_input_edges_and_returns_stored_reference(
    connection, monkeypatch
):
    case = _seed_summary_case(connection)
    # Existing storage accepts nonblank references without an APP format/length
    # rule. Internal whitespace and canonical case must not be rewritten.
    reference = f"Office  MiXeD {case['applicant'].hex}" + "-Long" * 80
    connection.execute(
        "update lending.client_onboarding_applicants set application_reference = %s "
        "where id = %s",
        (reference, case["applicant"]),
    )
    repository = _repository(connection, monkeypatch)
    before = _summary_state(connection, case)

    record = _method(repository)(
        application_reference=f" \t{reference.swapcase()}\r\n"
    )

    _assert_selection(record, case, reference)
    assert _summary_state(connection, case) == before


def test_identical_names_resolve_only_their_exact_office_references(
    connection, monkeypatch
):
    first = _seed_summary_case(connection)
    second = _seed_summary_case(connection)
    repository = _repository(connection, monkeypatch)
    first_reference = _reference(connection, first)
    second_reference = _reference(connection, second)
    before = _summary_state(connection, first)
    other_before = _summary_state(connection, second)
    assert before["applicant"]["full_name"] == other_before["applicant"]["full_name"]

    first_record = _method(repository)(application_reference=first_reference)
    second_record = _method(repository)(application_reference=second_reference)

    _assert_selection(first_record, first, first_reference)
    _assert_selection(second_record, second, second_reference)
    assert first_record.promoted_client_id != second_record.promoted_client_id
    assert _summary_state(connection, first) == before
    assert _summary_state(connection, second) == other_before


@pytest.mark.parametrize(
    "scenario", ["unknown", "partial", "wildcards", "sql_text", "identity_fields"]
)
def test_unmatched_references_do_not_search_or_fall_back_to_other_identity_fields(
    connection, monkeypatch, scenario
):
    case = _seed_summary_case(connection)
    reference = _reference(connection, case)
    repository = _repository(connection, monkeypatch)
    before = _summary_state(connection, case)
    client = next(row for row in before["clients"] if row["id"] == case["client"])
    references = {
        "unknown": [f"MISSING-OFFICE-{uuid4().hex}"],
        "partial": [reference[:-1], f"{reference}-different"],
        "wildcards": [f"{reference[:-1]}%", f"{reference[:-1]}_", "%"],
        "sql_text": [f"{reference}' OR 1=1 --"],
        "identity_fields": [
            str(case["client"]),
            str(case["applicant"]),
            client["client_code"],
            before["applicant"]["full_name"],
            before["applicant"]["phone_number"],
        ],
    }[scenario]

    for candidate in references:
        assert _method(repository)(application_reference=candidate) is None

    assert _summary_state(connection, case) == before


@pytest.mark.parametrize(
    "applicant_status",
    ["requirements_incomplete", "under_verification", "requirements_rejected"],
)
def test_ineligible_applicant_cannot_select_even_with_existing_client_link(
    connection, monkeypatch, applicant_status
):
    case = _seed_summary_case(connection)
    connection.execute(
        "update lending.client_onboarding_applicants set status = %s where id = %s",
        (applicant_status, case["applicant"]),
    )
    reference = _reference(connection, case)
    repository = _repository(connection, monkeypatch)
    before = _summary_state(connection, case)

    assert _method(repository)(application_reference=reference) is None

    assert _summary_state(connection, case) == before


def test_unpromoted_applicant_does_not_select_same_name_client_or_promote_itself(
    connection, monkeypatch
):
    case = _seed_summary_case(connection)
    # Eligible+NULL is forbidden by the existing schema. Use a real valid intake
    # row and leave its former stable Client present to expose identity fallback.
    connection.execute(
        "update lending.client_onboarding_applicants "
        "set status = 'under_verification', promoted_client_id = NULL, "
        "full_name = 'Synthetic CIF Borrower' where id = %s",
        (case["applicant"],),
    )
    reference = _reference(connection, case)
    repository = _repository(connection, monkeypatch)
    before = _summary_state(connection, case)

    assert _method(repository)(application_reference=reference) is None

    assert _summary_state(connection, case) == before


@pytest.mark.parametrize("client_status", ["blocked", "closed"])
def test_unavailable_client_cannot_be_selected_from_eligible_applicant(
    connection, monkeypatch, client_status
):
    case = _seed_summary_case(connection)
    connection.execute(
        "update lending.clients set status = %s where id = %s",
        (client_status, case["client"]),
    )
    reference = _reference(connection, case)
    repository = _repository(connection, monkeypatch)
    before = _summary_state(connection, case)

    assert _method(repository)(application_reference=reference) is None

    assert _summary_state(connection, case) == before


def test_eligible_selection_does_not_require_or_create_a_cif(connection, monkeypatch):
    case = _seed_summary_case(connection)
    connection.execute(
        "delete from lending.client_cif_versions where client_id = %s",
        (case["client"],),
    )
    reference = _reference(connection, case)
    repository = _repository(connection, monkeypatch)
    before = _summary_state(connection, case)
    assert before["versions"] == []

    record = _method(repository)(application_reference=reference)

    _assert_selection(record, case, reference)
    assert _summary_state(connection, case) == before


def test_repeated_selection_preserves_confirmation_and_state_in_read_only_transaction(
    connection, monkeypatch
):
    case = _seed_summary_case(connection)
    confirmation = _insert(connection, case)
    reference = _reference(connection, case)
    repository = _repository(connection, monkeypatch)
    before = _summary_state(connection, case)
    # PostgreSQL itself rejects data writes and SELECT FOR UPDATE/SHARE here,
    # even when fixture foreign keys have already acquired source-table locks.
    connection.execute("SET LOCAL transaction_read_only = on")

    first = _method(repository)(application_reference=reference)
    repeated = _method(repository)(application_reference=reference.lower())

    _assert_selection(first, case, reference)
    assert repeated == first
    assert _read(connection, confirmation["id"]) == confirmation
    assert _summary_state(connection, case) == before


def test_invalid_reference_values_raise_value_error_without_changing_state(
    connection, monkeypatch
):
    case = _seed_summary_case(connection)
    repository = _repository(connection, monkeypatch)
    method = _method(repository)
    before = _summary_state(connection, case)

    def reject_database_access():
        pytest.fail("Invalid references must be rejected before database access")

    monkeypatch.setattr(import_module(MODULE), "open_connection", reject_database_access)

    for value in (None, 17, True, case["client"], [], {}, "", " \t\r\n"):
        with pytest.raises(ValueError):
            method(application_reference=value)

    assert _summary_state(connection, case) == before


def test_office_reference_is_owned_by_intake_not_per_loan_application_history(
    connection, monkeypatch
):
    case = _seed_summary_case(connection)
    other = _seed_summary_case(connection)
    office_reference = _reference(connection, case)
    loan_only_reference = f"SYN-LOAN-ONLY-{uuid4().hex}"
    for reference in (office_reference, loan_only_reference):
        connection.execute(
            "insert into lending.loan_applications "
            "(application_reference, client_id, created_by_user_id) values (%s, %s, %s)",
            (reference, other["client"], other["actor"]),
        )
    repository = _repository(connection, monkeypatch)
    before = _summary_state(connection, case)
    other_before = _summary_state(connection, other)
    history_before = connection.execute(
        "select * from lending.loan_applications where client_id = %s order by id",
        (other["client"],),
    ).fetchall()

    record = _method(repository)(application_reference=office_reference)
    absent = _method(repository)(application_reference=loan_only_reference)

    _assert_selection(record, case, office_reference)
    assert absent is None
    assert _summary_state(connection, case) == before
    assert _summary_state(connection, other) == other_before
    assert connection.execute(
        "select * from lending.loan_applications where client_id = %s order by id",
        (other["client"],),
    ).fetchall() == history_before
