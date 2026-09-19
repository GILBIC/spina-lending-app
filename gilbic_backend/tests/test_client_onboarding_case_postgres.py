"""Actual PostgreSQL proof for role-scoped pre-CIF case reads."""
from __future__ import annotations

from contextlib import contextmanager
from uuid import uuid4

import pytest

from test_client_cif_review_confirmation_postgres import (
    DATABASE_URL, _seed_summary_case, _summary_state,
    connection as connection, runtime_url as runtime_url,
)


pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="GILBIC_TEST_DATABASE_URL is not configured")


def _repository(connection, monkeypatch):
    from gilbic_backend import client_onboarding_repository as module

    @contextmanager
    def acquire():
        with connection.transaction():
            yield connection

    monkeypatch.setattr(module, "open_connection", acquire)
    return module.PostgresClientOnboardingRepository()


def _case(connection, role="employee", status="requirements_incomplete"):
    case = _seed_summary_case(connection)
    connection.execute("update core.users set status = 'active' where id = %s", (case["actor"],))
    connection.execute(
        "insert into core.user_roles (user_id, role_id) select %s, id from core.roles where code = %s",
        (case["actor"], role),
    )
    reference = f"Office / MiXeD  {case['applicant'].hex}"
    connection.execute(
        """update lending.client_onboarding_applicants
           set application_reference = %s, status = %s,
               promoted_client_id = case when %s = 'eligible_for_cif' then promoted_client_id else null end,
               national_id_status = 'passed', tin_id_status = 'failed', meralco_bill_status = 'pending',
               collector_visit_status = 'pending', collector_visit_note = 'Synthetic prior visit note'
           where id = %s""",
        (reference, status, status, case["applicant"]),
    )
    case["reference"] = reference
    return case


def _read(repository, case, scope="office", reference=None):
    return repository.get_case_by_reference(actor_user_id=case["actor"], scope=scope,
        application_reference=reference if reference is not None else case["reference"])


@pytest.mark.parametrize("role", ["employee", "management"])
@pytest.mark.parametrize("status", ["requirements_incomplete", "under_verification", "requirements_rejected", "eligible_for_cif"])
def test_exact_office_case_includes_unpromoted_applicants_and_preserves_truthful_statuses(connection, monkeypatch, role, status):
    case = _case(connection, role, status)
    repository = _repository(connection, monkeypatch)
    before = _summary_state(connection, case)
    result = _read(repository, case, reference=f" \t{case['reference'].lower()} ")
    assert result["applicant_id"] == case["applicant"]
    assert result["application_reference"] == case["reference"]
    assert result["status"] == status
    assert result["client_id"] == (case["client"] if status == "eligible_for_cif" else None)
    assert result["requirements"]["national_id"] == {"status": "passed", "evidence_reference": "SYNTHETIC-NATIONAL"}
    assert result["requirements"]["tin_id"]["status"] == "failed"
    assert result["requirements"]["collector_visit"]["status"] == "pending"
    assert result["bypassed_requirements"] == []
    assert result["privacy_consent"] is True
    assert _read(repository, case) == result
    assert _summary_state(connection, case) == before


def test_collector_projection_excludes_government_evidence_email_consent_and_client_link(connection, monkeypatch):
    case = _case(connection, "collector")
    result = _read(_repository(connection, monkeypatch), case, "collector")
    assert set(result) == {"applicant_id", "application_reference", "status", "full_name", "phone_number", "present_address", "collector_visit"}
    assert result["collector_visit"] == {"status": "pending", "note": "Synthetic prior visit note", "evidence_reference": "SYNTHETIC-VISIT"}
    assert "SYNTHETIC-NATIONAL" not in str(result)


@pytest.mark.parametrize("role,scope", [("collector", "office"), ("employee", "collector"), ("management", "collector"), ("client", "office")])
def test_wrong_persisted_role_cannot_read_case(connection, monkeypatch, role, scope):
    from gilbic_backend.client_onboarding_repository import ClientOnboardingAccessDenied
    case = _case(connection, role)
    with pytest.raises(ClientOnboardingAccessDenied):
        _read(_repository(connection, monkeypatch), case, scope)


@pytest.mark.parametrize("revocation", ["status", "role", "permission"])
def test_persisted_access_revocation_blocks_subsequent_read(connection, monkeypatch, revocation):
    from gilbic_backend.client_onboarding_repository import ClientOnboardingAccessDenied
    case = _case(connection)
    repository = _repository(connection, monkeypatch)
    assert _read(repository, case) is not None
    if revocation == "status":
        connection.execute("update core.users set status = 'inactive' where id = %s", (case["actor"],))
    elif revocation == "role":
        connection.execute("delete from core.user_roles where user_id = %s", (case["actor"],))
    else:
        connection.execute("delete from core.role_permissions where role_id in (select id from core.roles where code = 'employee') and permission_code = 'client_onboarding.requirement.review'")
    with pytest.raises(ClientOnboardingAccessDenied):
        _read(repository, case)


def test_exact_reference_never_falls_back_to_same_name_uuid_wildcards_or_sql(connection, monkeypatch):
    first = _case(connection)
    second = _case(connection)
    repository = _repository(connection, monkeypatch)
    assert _read(repository, first)["applicant_id"] != _read(repository, second)["applicant_id"]
    for reference in [str(first["applicant"]), "Synthetic Intake Name", "%", first["reference"] + "%", "' OR 1=1 --", str(uuid4())]:
        assert _read(repository, first, reference=reference) is None


@pytest.mark.parametrize("reference", [None, 42, "", " \t\n "])
def test_invalid_reference_fails_before_any_database_access(monkeypatch, reference):
    from gilbic_backend import client_onboarding_repository as module
    def forbidden():
        pytest.fail("Invalid reference must not acquire a connection")
    monkeypatch.setattr(module, "open_connection", forbidden)
    with pytest.raises(ValueError):
        module.PostgresClientOnboardingRepository().get_case_by_reference(
            actor_user_id=uuid4(), application_reference=reference, scope="office")
