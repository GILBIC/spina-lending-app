"""Office entry context is advisory and never changes saved application sources."""
from __future__ import annotations

from dataclasses import asdict
from uuid import uuid4

import psycopg
import pytest

from gilbic_backend.loan_application_repository import (
    LoanApplicationAccessDenied,
    LoanApplicationConflict,
)
from test_loan_application_repository_postgres import (
    DATABASE_URL,
    _append,
    _create,
    _repository,
    _seed,
    _state,
    connection as connection,
    runtime_url as runtime_url,
)


pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="GILBIC_TEST_DATABASE_URL is not configured",
)
UNAVAILABLE = "No eligible current CIF is available for this application draft."


def _context(repository, case, **changes):
    return repository.get_entry_context(**{
        "actor_user_id": case["actor"], "client_id": case["client"], **changes,
    })


def _catalog(connection):
    connection.execute("update lending.loan_types set is_active = false")
    options = [
        {"id": uuid4(), "code": f"A-{uuid4().hex}", "name": "Synthetic Same Name"},
        {"id": uuid4(), "code": f"B-{uuid4().hex}", "name": "Synthetic Same Name"},
        {"id": uuid4(), "code": f"Z-{uuid4().hex}", "name": "Synthetic Zulu"},
    ]
    for option in reversed(options):
        connection.execute(
            "insert into lending.loan_types (id, code, name, term_days, calculation_mode) "
            "values (%(id)s, %(code)s, %(name)s, 60, 'custom')", option,
        )
    connection.execute(
        "insert into lending.loan_types (code, name, term_days, calculation_mode, is_active) "
        "values (%s, 'Synthetic Hidden Inactive', 60, 'custom', false)",
        (f"INACTIVE-{uuid4().hex}",),
    )
    return options


@pytest.mark.parametrize("role", ["employee", "management"])
@pytest.mark.parametrize("client_status,cif_status", [
    ("inactive", "draft"), ("active", "draft"),
    ("inactive", "active"), ("active", "active"),
])
def test_entry_context_preserves_existing_eligibility_and_only_reads(
    connection, monkeypatch, role, client_status, cif_status,
):
    repository = _repository(connection, monkeypatch)
    case = _seed(connection, role)
    _seed(connection)  # Another eligible Client cannot supply this context's CIF.
    connection.execute(
        "update lending.clients set status = %s where id = %s", (client_status, case["client"]),
    )
    if cif_status == "active":
        connection.execute(
            "update lending.client_cif_versions set status = 'active', "
            "baseline_liveness_status = 'passed', baseline_face_scan_evidence_reference = 'SYNTHETIC-FACE', "
            "activated_at = now(), expires_at = now() + interval '5 years', "
            "review_due_at = now() + interval '5 years' - interval '90 days' where id = %s",
            (case["cif"],),
        )
    expected = _catalog(connection)
    before = _state(connection, case)
    catalog_before = connection.execute("select * from lending.loan_types order by id").fetchall()
    statements = []

    class RecordingCursor(psycopg.Cursor):
        def execute(self, query, params=None, **kwargs):
            statements.append(" ".join(query.lower().split()))
            return super().execute(query, params, **kwargs)

    original_factory = connection.cursor_factory
    connection.cursor_factory = RecordingCursor
    try:
        context = _context(repository, case)
    finally:
        connection.cursor_factory = original_factory

    assert context.client_id == case["client"]
    assert context.cif_version_id == case["cif"]
    assert context.cif_version_number == 1  # A newer noncurrent version is not selected.
    assert [asdict(option) for option in context.loan_types] == expected
    assert statements and all(query.startswith("select ") for query in statements)
    assert all("for update" not in query and "for share" not in query for query in statements)
    assert _state(connection, case) == before
    assert connection.execute("select * from lending.loan_types order by id").fetchall() == catalog_before


@pytest.mark.parametrize("scenario", [
    "unknown_client", "no_current", "superseded", "blocked", "closed",
    "ineligible", "missing_applicant", "wrong_promoted_client",
])
def test_unavailable_sources_return_one_generic_conflict_without_side_effects(
    connection, monkeypatch, scenario,
):
    repository = _repository(connection, monkeypatch)
    case = _seed(connection)
    client_id = case["client"]
    if scenario == "unknown_client":
        client_id = uuid4()
    elif scenario == "no_current":
        connection.execute(
            "update lending.client_cif_versions set is_current = false where id = %s", (case["cif"],),
        )
    elif scenario == "superseded":
        connection.execute(
            "update lending.client_cif_versions set status = 'superseded' where id = %s", (case["cif"],),
        )
    elif scenario in {"blocked", "closed"}:
        connection.execute("update lending.clients set status = %s where id = %s", (scenario, client_id))
    elif scenario == "ineligible":
        connection.execute(
            "update lending.client_onboarding_applicants set status = 'requirements_rejected' "
            "where id = %s", (case["applicant"],),
        )
    elif scenario == "missing_applicant":
        connection.execute(
            "delete from lending.client_onboarding_applicants where id = %s", (case["applicant"],),
        )
    else:
        connection.execute(
            "update lending.client_onboarding_applicants set promoted_client_id = %s where id = %s",
            (case["other"], case["applicant"]),
        )
    before = _state(connection, case)

    with pytest.raises(LoanApplicationConflict) as error:
        _context(repository, case, client_id=client_id)
    assert str(error.value) == UNAVAILABLE
    assert _state(connection, case) == before


def test_fresh_context_tracks_current_cif_without_changing_old_context(connection, monkeypatch):
    repository = _repository(connection, monkeypatch)
    case = _seed(connection)
    first = _context(repository, case)
    connection.execute(
        "update lending.client_cif_versions set is_current = false, status = 'superseded' where id = %s",
        (case["cif"],),
    )
    connection.execute(
        "update lending.client_cif_versions set is_current = true where id = %s", (case["next_cif"],),
    )
    before = _state(connection, case)

    current = _context(repository, case)

    assert first.cif_version_id == case["cif"] and first.cif_version_number == 1
    assert current.cif_version_id == case["next_cif"] and current.cif_version_number == 2
    assert _state(connection, case) == before


def test_empty_active_catalog_still_returns_eligible_cif(connection, monkeypatch):
    repository = _repository(connection, monkeypatch)
    case = _seed(connection)
    connection.execute("update lending.loan_types set is_active = false")
    before = _state(connection, case)

    context = _context(repository, case)

    assert context.loan_types == ()
    assert context.cif_version_id == case["cif"]
    assert _state(connection, case) == before


@pytest.mark.parametrize("denial", ["collector", "inactive", "no_permission"])
def test_entry_context_requires_persisted_office_authority(connection, monkeypatch, denial):
    repository = _repository(connection, monkeypatch)
    case = _seed(connection)
    actor_id = case["actor"]
    if denial == "collector":
        actor_id = _seed(connection, "collector")["actor"]
    elif denial == "inactive":
        connection.execute("update core.users set status = 'inactive' where id = %s", (actor_id,))
    else:
        connection.execute(
            "delete from core.role_permissions where permission_code = %s",
            ("client_onboarding.requirement.review",),
        )
    before = _state(connection, case)

    with pytest.raises(LoanApplicationAccessDenied):
        _context(repository, case, actor_user_id=actor_id)
    assert _state(connection, case) == before


@pytest.mark.parametrize("operation", ["create", "append"])
def test_context_does_not_bypass_save_recheck_after_current_cif_changes(
    connection, monkeypatch, operation,
):
    repository = _repository(connection, monkeypatch)
    case = _seed(connection)
    first = _create(repository, case, f"SYN-ENTRY-{uuid4().hex}")
    context = _context(repository, case)
    connection.execute(
        "update lending.client_cif_versions set is_current = false, status = 'superseded' where id = %s",
        (case["cif"],),
    )
    connection.execute(
        "update lending.client_cif_versions set is_current = true where id = %s", (case["next_cif"],),
    )
    before = _state(connection, case)

    with pytest.raises(LoanApplicationConflict) as error:
        if operation == "create":
            _create(repository, case, f"SYN-ENTRY-{uuid4().hex}", cif_version_id=context.cif_version_id)
        else:
            _append(repository, case, first, cif_version_id=context.cif_version_id)
    assert str(error.value) == UNAVAILABLE
    assert _state(connection, case) == before
