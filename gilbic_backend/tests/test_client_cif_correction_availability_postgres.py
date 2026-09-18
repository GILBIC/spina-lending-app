"""Real, read-only availability projection using the guarded CIF fixtures."""
from __future__ import annotations

import psycopg
import pytest

from test_client_cif_review_confirmation_postgres import (
    DATABASE_URL,
    _insert,
    _seed_summary_case,
    _summary_repository,
    _summary_state,
    connection as connection,
    runtime_url as runtime_url,
)


pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="GILBIC_TEST_DATABASE_URL is not configured",
)


def _read(repository, client_id):
    return repository.get_review_summary(
        client_id=client_id, include_correction_availability=True,
    )


@pytest.mark.parametrize(
    "cif_status,client_status,expected",
    [
        ("draft", "inactive", True),
        ("draft", "active", False),
        ("active", "inactive", False),
        ("active", "active", False),
    ],
)
def test_availability_is_read_with_same_summary_without_writes(
    connection, monkeypatch, cif_status, client_status, expected,
):
    case = _seed_summary_case(connection)
    connection.execute(
        "update lending.clients set status = %s where id = %s",
        (client_status, case["client"]),
    )
    if cif_status == "active":
        connection.execute(
            """
            update lending.client_cif_versions
            set status = 'active', baseline_liveness_status = 'passed',
                baseline_face_scan_evidence_reference = 'SYNTHETIC-FACE',
                activated_at = now(), expires_at = now() + interval '5 years',
                review_due_at = now() + interval '5 years' - interval '90 days'
            where id = %s
            """,
            (case["cif"],),
        )
    repository = _summary_repository(connection, monkeypatch)
    before = _summary_state(connection, case)
    statements = []

    class RecordingCursor(psycopg.Cursor):
        def execute(self, query, params=None, **kwargs):
            statements.append((" ".join(query.lower().split()), params))
            return super().execute(query, params, **kwargs)

    original_factory = connection.cursor_factory
    connection.cursor_factory = RecordingCursor
    try:
        record = _read(repository, case["client"])
    finally:
        connection.cursor_factory = original_factory

    assert record.id == case["cif"] and record.client_id == case["client"]
    assert record.can_correct_information is expected
    assert len(statements) == 1
    query, params = statements[0]
    assert query.startswith("select ")
    assert "from lending.client_cif_versions cif" in query
    assert "from lending.client_cif_review_confirmations" in query
    assert params == (case["client"],)
    assert "for update" not in query and "for share" not in query
    assert _summary_state(connection, case) == before
    default_record = repository.get_review_summary(client_id=case["client"])
    assert not hasattr(default_record, "can_correct_information")


def test_confirmed_current_draft_is_not_correctable(connection, monkeypatch):
    case = _seed_summary_case(connection)
    _insert(connection, case)
    repository = _summary_repository(connection, monkeypatch)
    before = _summary_state(connection, case)

    record = _read(repository, case["client"])

    assert record.status == "draft"
    assert record.can_correct_information is False
    assert _summary_state(connection, case) == before


@pytest.mark.parametrize("confirmed_source", ["previous_version", "another_client"])
def test_other_confirmation_does_not_disable_current_unconfirmed_draft(
    connection, monkeypatch, confirmed_source,
):
    case = _seed_summary_case(connection)
    other = _seed_summary_case(connection)
    if confirmed_source == "previous_version":
        _insert(connection, case)
        connection.execute(
            "update lending.client_cif_versions set is_current = false, status = 'superseded' "
            "where id = %s", (case["cif"],),
        )
        connection.execute(
            "update lending.client_cif_versions set is_current = true where id = %s",
            (case["next_cif"],),
        )
    else:
        _insert(connection, other)
    repository = _summary_repository(connection, monkeypatch)
    before = _summary_state(connection, case)
    other_before = _summary_state(connection, other)

    assert _read(repository, case["client"]).can_correct_information is True

    assert _summary_state(connection, case) == before
    assert _summary_state(connection, other) == other_before


@pytest.mark.parametrize("scenario", ["ineligible_intake", "wrong_link", "noncurrent", "blocked"])
def test_opt_in_keeps_unavailable_sources_out_of_summary(connection, monkeypatch, scenario):
    from gilbic_backend.client_cif_repository import ClientCifConflict

    case = _seed_summary_case(connection)
    if scenario == "ineligible_intake":
        connection.execute(
            "update lending.client_onboarding_applicants set status = 'under_verification' "
            "where id = %s", (case["applicant"],),
        )
    elif scenario == "wrong_link":
        connection.execute(
            "update lending.client_onboarding_applicants set promoted_client_id = %s "
            "where id = %s", (case["other"], case["applicant"]),
        )
    elif scenario == "noncurrent":
        connection.execute(
            "update lending.client_cif_versions set is_current = false where id = %s",
            (case["cif"],),
        )
    else:
        connection.execute(
            "update lending.clients set status = 'blocked' where id = %s",
            (case["client"],),
        )
    repository = _summary_repository(connection, monkeypatch)
    before = _summary_state(connection, case)

    with pytest.raises(ClientCifConflict):
        _read(repository, case["client"])

    assert _summary_state(connection, case) == before
