"""Promoted intake re-review against real PostgreSQL rows, constraints and locks."""

from contextlib import contextmanager
from dataclasses import replace

import psycopg
import pytest
from gilbic_backend.auth_api import account_repository_dependency
from gilbic_backend.client_onboarding_api import client_onboarding_repository_dependency
from gilbic_backend.client_onboarding_repository import (
    ClientOnboardingConflict,
    PostgresClientOnboardingRepository,
)
from psycopg.rows import dict_row
from test_client_onboarding_promotion_postgres import (
    DATABASE_URL,
    _delete_case,
    _seed_case,
)
from test_client_onboarding_promotion_postgres import (
    use_test_database as use_test_database,  # noqa: PLC0414 -- pytest fixture
)
from test_client_onboarding_review_api import _client_for, _document_body, _headers

from gilbic_backend import client_onboarding_repository as module

pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="GILBIC_TEST_DATABASE_URL is not configured"
)


@pytest.fixture
def promoted_case():
    case = _seed_case()
    try:
        repository = PostgresClientOnboardingRepository()
        promoted = repository.approve_normal_eligibility(
            actor_user_id=case.actor_user_id, applicant_id=case.applicant_id
        )
        yield case, repository, promoted.promoted_client_id
    finally:
        _delete_case(case)


def _state(case):
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        applicant = connection.execute(
            "select * from lending.client_onboarding_applicants where id = %s",
            (case.applicant_id,),
        ).fetchone()
        clients = connection.execute(
            "select * from lending.clients where client_code = %s order by id",
            (case.expected_client_code,),
        ).fetchall()
        audit = connection.execute(
            "select * from core.audit_logs where actor_user_id = %s order by id",
            (case.actor_user_id,),
        ).fetchall()
    return {"applicant": applicant, "clients": clients, "audit": audit}


def _review(repository, case, **changes):
    return repository.review_document_requirements(
        actor_user_id=case.actor_user_id,
        applicant_id=case.applicant_id,
        **{**_document_body(), **changes},
    )


def test_promoted_review_replay_retains_one_client_and_cif_selection(promoted_case):
    case, repository, client_id = promoted_case
    before = _state(case)
    assert len(before["clients"]) == 1
    for _ in range(2):
        reviewed = _review(repository, case)
        approved = repository.approve_normal_eligibility(
            actor_user_id=case.actor_user_id, applicant_id=case.applicant_id
        )
        selected = repository.find_cif_client_by_reference(
            application_reference=case.application_reference
        )
        assert (
            reviewed.status == approved.status == selected.status == "eligible_for_cif"
        )
        assert reviewed.promoted_client_id == approved.promoted_client_id == client_id
        assert selected.promoted_client_id == client_id
    # Includes timestamps and audits: exact replay must not write another decision.
    assert _state(case) == before


@pytest.mark.parametrize(
    "field", ["national_id_status", "tin_id_status", "meralco_bill_status"]
)
def test_promoted_requirement_change_conflicts_without_database_mutation(
    promoted_case, field
):
    case, repository, client_id = promoted_case
    before = _state(case)
    with pytest.raises(ClientOnboardingConflict, match="promoted"):
        _review(repository, case, **{field: "failed"})
    assert _state(case) == before
    assert before["applicant"]["promoted_client_id"] == client_id
    assert len(before["clients"]) == 1


def test_promoted_requirement_change_http_409_preserves_database_identity(
    promoted_case,
):
    case, repository, _ = promoted_case
    before = _state(case)
    client, _ = _client_for(
        role="management", permissions=("client_onboarding.requirement.review",)
    )
    accounts = client.app.dependency_overrides[account_repository_dependency]()
    accounts.context = replace(accounts.context, user_id=case.actor_user_id)
    client.app.dependency_overrides[client_onboarding_repository_dependency] = lambda: (
        repository
    )
    with client:
        response = client.patch(
            f"/api/v1/management/onboarding/applicants/{case.applicant_id}/document-requirements",
            headers=_headers(),
            json={**_document_body(), "national_id_status": "failed"},
        )
    assert response.status_code == 409
    assert "promoted" in response.json()["detail"]
    assert _state(case) == before


@pytest.mark.parametrize("bypass", [False, True])
def test_legacy_demoted_identity_conflicts_before_duplicate_promotion(
    promoted_case, bypass
):
    case, repository, client_id = promoted_case
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        connection.execute(
            """update lending.client_onboarding_applicants
               set status = 'under_verification', national_id_status = %s
               where id = %s""",
            ("failed" if bypass else "passed", case.applicant_id),
        )
    before = _state(case)
    with pytest.raises(ClientOnboardingConflict, match="promoted"):
        if bypass:
            repository.bypass_and_approve_eligibility(
                actor_user_id=case.actor_user_id,
                applicant_id=case.applicant_id,
                bypassed_requirements=["national_id"],
                reason="Synthetic reviewed exception",
            )
        else:
            repository.approve_normal_eligibility(
                actor_user_id=case.actor_user_id, applicant_id=case.applicant_id
            )
    assert _state(case) == before
    assert before["clients"][0]["id"] == client_id
    assert len(before["clients"]) == 1


def test_promoted_replay_waits_for_row_lock_before_deciding(promoted_case, monkeypatch):
    case, repository, client_id = promoted_case
    assert DATABASE_URL is not None
    before = _state(case)

    @contextmanager
    def bounded_connection():
        with psycopg.connect(DATABASE_URL) as connection:
            connection.execute("set local lock_timeout = '100ms'")
            yield connection

    monkeypatch.setattr(module, "open_connection", bounded_connection)
    with psycopg.connect(DATABASE_URL) as locker:
        locker.execute(
            "select id from lending.client_onboarding_applicants where id = %s for update",
            (case.applicant_id,),
        )
        with pytest.raises(psycopg.errors.LockNotAvailable):
            _review(repository, case)
    # After the competing transaction releases its lock, the same replay succeeds.
    assert _review(repository, case).promoted_client_id == client_id
    assert _state(case) == before
