from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from uuid import UUID, uuid4

import gilbic_backend.client_onboarding_repository as client_onboarding_repository_module
import psycopg
import pytest
from gilbic_backend.client_onboarding_repository import PostgresClientOnboardingRepository
from psycopg.rows import dict_row


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)


@contextmanager
def _test_connection():
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        yield connection


@dataclass(frozen=True, slots=True)
class OnboardingPromotionCase:
    actor_user_id: UUID
    applicant_id: UUID
    application_reference: str
    expected_client_code: str


def _seed_case(*, non_passed_requirement: str | None = None) -> OnboardingPromotionCase:
    assert DATABASE_URL is not None
    statuses = {
        "national_id": "passed",
        "tin_id": "passed",
        "meralco_bill": "passed",
        "collector_visit": "passed",
    }
    if non_passed_requirement is not None:
        statuses[non_passed_requirement] = "pending"

    actor_user_id = uuid4()
    applicant_id = uuid4()
    token = uuid4().hex[:12]
    with psycopg.connect(DATABASE_URL) as connection:
        sequence_value = connection.execute(
            "select nextval('lending.client_onboarding_reference_seq')"
        ).fetchone()[0]
        application_reference = f"APP-2026-{int(sequence_value):06d}"
        expected_client_code = application_reference.replace("APP-", "CLIENT-", 1)
        connection.execute(
            """
            insert into core.users (id, username, email, full_name, status)
            values (%s, %s, %s, 'Onboarding Reviewer', 'active')
            """,
            (
                actor_user_id,
                f"onboarding-reviewer-{token}",
                f"onboarding-reviewer-{token}@example.com",
            ),
        )
        connection.execute(
            """
            insert into lending.client_onboarding_applicants (
                id,
                application_reference,
                status,
                full_name,
                phone_number,
                email,
                present_address,
                national_id_egov_evidence_reference,
                national_id_status,
                tin_id_egov_evidence_reference,
                tin_id_status,
                meralco_bill_evidence_reference,
                meralco_bill_status,
                collector_visit_status,
                privacy_consent,
                accuracy_declaration
            )
            values (
                %s, %s, 'under_verification', 'Maria Santos', '09171234567',
                'maria@example.com', '123 Test Street, Rizal',
                'FAKE-NATIONAL-ID', %s,
                'FAKE-TIN-ID', %s,
                'FAKE-MERALCO', %s,
                %s, true, true
            )
            """,
            (
                applicant_id,
                application_reference,
                statuses["national_id"],
                statuses["tin_id"],
                statuses["meralco_bill"],
                statuses["collector_visit"],
            ),
        )

    return OnboardingPromotionCase(
        actor_user_id=actor_user_id,
        applicant_id=applicant_id,
        application_reference=application_reference,
        expected_client_code=expected_client_code,
    )


def _set_all_requirements_pending(case: OnboardingPromotionCase) -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        connection.execute(
            """
            update lending.client_onboarding_applicants
            set
                national_id_status = 'pending',
                tin_id_status = 'pending',
                meralco_bill_status = 'pending',
                collector_visit_status = 'pending',
                updated_at = now()
            where id = %s
            """,
            (case.applicant_id,),
        )


def _delete_case(case: OnboardingPromotionCase) -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        promoted = connection.execute(
            """
            select promoted_client_id
            from lending.client_onboarding_applicants
            where id = %s
            """,
            (case.applicant_id,),
        ).fetchone()
        promoted_client_id = promoted[0] if promoted is not None else None
        target_ids = [case.applicant_id]
        if promoted_client_id is not None:
            target_ids.append(promoted_client_id)

        connection.execute(
            """
            delete from core.audit_logs
            where actor_user_id = %s or target_id = any(%s)
            """,
            (case.actor_user_id, target_ids),
        )
        connection.execute(
            "delete from lending.client_onboarding_applicants where id = %s",
            (case.applicant_id,),
        )
        if promoted_client_id is not None:
            connection.execute(
                "delete from lending.clients where id = %s",
                (promoted_client_id,),
            )
        connection.execute(
            "delete from core.users where id = %s",
            (case.actor_user_id,),
        )


@pytest.fixture(autouse=True)
def use_test_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        client_onboarding_repository_module,
        "open_connection",
        _test_connection,
    )


def test_normal_eligibility_promotion_is_atomic_idempotent_and_non_financial() -> None:
    case = _seed_case()
    try:
        repository = PostgresClientOnboardingRepository()
        assert DATABASE_URL is not None

        with psycopg.connect(DATABASE_URL) as connection:
            user_count_before = connection.execute(
                "select count(*) from core.users"
            ).fetchone()[0]
            loan_count_before = connection.execute(
                "select count(*) from lending.loans"
            ).fetchone()[0]

        first = repository.approve_normal_eligibility(
            actor_user_id=case.actor_user_id,
            applicant_id=case.applicant_id,
        )
        second = repository.approve_normal_eligibility(
            actor_user_id=case.actor_user_id,
            applicant_id=case.applicant_id,
        )

        assert first.status == "eligible_for_cif"
        assert first.promoted_client_id is not None
        assert first.promoted_client_id == second.promoted_client_id

        with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
            client_row = connection.execute(
                """
                select id, client_code, full_name, phone_number, area, status, user_id
                from lending.clients
                where id = %s
                """,
                (first.promoted_client_id,),
            ).fetchone()
            onboarding_row = connection.execute(
                """
                select status, promoted_client_id,
                       eligibility_reviewed_by_user_id, eligibility_reviewed_at
                from lending.client_onboarding_applicants
                where id = %s
                """,
                (case.applicant_id,),
            ).fetchone()
            user_count_after = connection.execute(
                "select count(*) as count from core.users"
            ).fetchone()["count"]
            loan_count_after = connection.execute(
                "select count(*) as count from lending.loans"
            ).fetchone()["count"]
            matching_client_count = connection.execute(
                """
                select count(*) as count
                from lending.clients
                where client_code = %s
                """,
                (case.expected_client_code,),
            ).fetchone()["count"]
            audit_rows = connection.execute(
                """
                select action, target_type, target_id
                from core.audit_logs
                where actor_user_id = %s
                  and target_id = any(%s)
                order by action
                """,
                (
                    case.actor_user_id,
                    [case.applicant_id, first.promoted_client_id],
                ),
            ).fetchall()

        assert client_row is not None
        assert client_row["client_code"] == case.expected_client_code
        assert client_row["full_name"] == "Maria Santos"
        assert client_row["phone_number"] == "09171234567"
        assert client_row["area"] is None
        assert client_row["status"] == "inactive"
        assert client_row["user_id"] is None
        assert onboarding_row["status"] == "eligible_for_cif"
        assert onboarding_row["promoted_client_id"] == first.promoted_client_id
        assert onboarding_row["eligibility_reviewed_by_user_id"] == case.actor_user_id
        assert onboarding_row["eligibility_reviewed_at"] is not None
        assert user_count_after == user_count_before
        assert loan_count_after == loan_count_before
        assert matching_client_count == 1
        assert [row["action"] for row in audit_rows] == [
            "client_onboarding.client_created",
            "client_onboarding.eligibility_approved",
        ]
    finally:
        _delete_case(case)


@pytest.mark.parametrize(
    "non_passed_requirement",
    ["national_id", "tin_id", "meralco_bill", "collector_visit"],
)
def test_normal_eligibility_does_not_promote_when_any_requirement_is_not_passed(
    non_passed_requirement: str,
) -> None:
    case = _seed_case(non_passed_requirement=non_passed_requirement)
    try:
        repository = PostgresClientOnboardingRepository()
        record = repository.approve_normal_eligibility(
            actor_user_id=case.actor_user_id,
            applicant_id=case.applicant_id,
        )

        assert record.status != "eligible_for_cif"
        assert record.promoted_client_id is None

        assert DATABASE_URL is not None
        with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
            onboarding_row = connection.execute(
                """
                select status, promoted_client_id
                from lending.client_onboarding_applicants
                where id = %s
                """,
                (case.applicant_id,),
            ).fetchone()
            matching_client_count = connection.execute(
                """
                select count(*) as count
                from lending.clients
                where client_code = %s
                """,
                (case.expected_client_code,),
            ).fetchone()["count"]

        assert onboarding_row["status"] == "under_verification"
        assert onboarding_row["promoted_client_id"] is None
        assert matching_client_count == 0
    finally:
        _delete_case(case)


def test_management_bypass_promotes_all_pending_without_faking_requirement_passes() -> None:
    case = _seed_case()
    _set_all_requirements_pending(case)
    all_requirements = (
        "collector_visit",
        "meralco_bill",
        "national_id",
        "tin_id",
    )
    try:
        repository = PostgresClientOnboardingRepository()
        assert DATABASE_URL is not None

        with psycopg.connect(DATABASE_URL) as connection:
            user_count_before = connection.execute(
                "select count(*) from core.users"
            ).fetchone()[0]
            loan_count_before = connection.execute(
                "select count(*) from lending.loans"
            ).fetchone()[0]

        first = repository.bypass_and_approve_eligibility(
            actor_user_id=case.actor_user_id,
            applicant_id=case.applicant_id,
            bypassed_requirements=all_requirements,
            reason="  Approved   Management exception  ",
        )
        second = repository.bypass_and_approve_eligibility(
            actor_user_id=case.actor_user_id,
            applicant_id=case.applicant_id,
            bypassed_requirements=all_requirements,
            reason="Approved Management exception",
        )

        assert first.status == "eligible_for_cif"
        assert first.promoted_client_id is not None
        assert first.promoted_client_id == second.promoted_client_id

        with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
            client_row = connection.execute(
                """
                select client_code, area, status, user_id
                from lending.clients
                where id = %s
                """,
                (first.promoted_client_id,),
            ).fetchone()
            onboarding_row = connection.execute(
                """
                select
                    status,
                    promoted_client_id,
                    national_id_status,
                    tin_id_status,
                    meralco_bill_status,
                    collector_visit_status,
                    bypassed_requirements,
                    bypass_reason,
                    bypassed_by_user_id,
                    bypassed_at
                from lending.client_onboarding_applicants
                where id = %s
                """,
                (case.applicant_id,),
            ).fetchone()
            audit_rows = connection.execute(
                """
                select action, target_type, target_id, details
                from core.audit_logs
                where actor_user_id = %s
                  and target_id = any(%s)
                order by action
                """,
                (
                    case.actor_user_id,
                    [case.applicant_id, first.promoted_client_id],
                ),
            ).fetchall()
            user_count_after = connection.execute(
                "select count(*) as count from core.users"
            ).fetchone()["count"]
            loan_count_after = connection.execute(
                "select count(*) as count from lending.loans"
            ).fetchone()["count"]
            matching_client_count = connection.execute(
                """
                select count(*) as count
                from lending.clients
                where client_code = %s
                """,
                (case.expected_client_code,),
            ).fetchone()["count"]

        assert client_row is not None
        assert client_row["client_code"] == case.expected_client_code
        assert client_row["area"] is None
        assert client_row["status"] == "inactive"
        assert client_row["user_id"] is None
        assert onboarding_row["status"] == "eligible_for_cif"
        assert onboarding_row["promoted_client_id"] == first.promoted_client_id
        assert onboarding_row["national_id_status"] == "pending"
        assert onboarding_row["tin_id_status"] == "pending"
        assert onboarding_row["meralco_bill_status"] == "pending"
        assert onboarding_row["collector_visit_status"] == "pending"
        assert onboarding_row["bypassed_requirements"] == list(all_requirements)
        assert onboarding_row["bypass_reason"] == "Approved Management exception"
        assert onboarding_row["bypassed_by_user_id"] == case.actor_user_id
        assert onboarding_row["bypassed_at"] is not None
        assert user_count_after == user_count_before
        assert loan_count_after == loan_count_before
        assert matching_client_count == 1

        actions = [row["action"] for row in audit_rows]
        assert actions.count("client_onboarding.requirements_bypassed") == 1
        assert actions.count("client_onboarding.client_created") == 1
        assert actions.count("client_onboarding.eligibility_approved") == 1
        bypass_audit = next(
            row
            for row in audit_rows
            if row["action"] == "client_onboarding.requirements_bypassed"
        )
        assert bypass_audit["target_type"] == "client_onboarding_applicant"
        assert bypass_audit["target_id"] == case.applicant_id
        assert bypass_audit["details"] == {
            "bypassed_requirements": list(all_requirements),
            "reason": "Approved Management exception",
        }
        assert "evidence" not in str(bypass_audit["details"]).lower()
    finally:
        _delete_case(case)


def test_management_bypass_set_must_match_all_current_non_passed_requirements() -> None:
    case = _seed_case()
    _set_all_requirements_pending(case)
    try:
        repository = PostgresClientOnboardingRepository()
        record = repository.bypass_and_approve_eligibility(
            actor_user_id=case.actor_user_id,
            applicant_id=case.applicant_id,
            bypassed_requirements=("national_id", "tin_id", "meralco_bill"),
            reason="Approved exception",
        )

        assert record.status == "under_verification"
        assert record.promoted_client_id is None

        assert DATABASE_URL is not None
        with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
            onboarding_row = connection.execute(
                """
                select status, promoted_client_id, bypassed_requirements,
                       bypass_reason, bypassed_by_user_id, bypassed_at
                from lending.client_onboarding_applicants
                where id = %s
                """,
                (case.applicant_id,),
            ).fetchone()
            matching_client_count = connection.execute(
                """
                select count(*) as count
                from lending.clients
                where client_code = %s
                """,
                (case.expected_client_code,),
            ).fetchone()["count"]
            bypass_audit_count = connection.execute(
                """
                select count(*) as count
                from core.audit_logs
                where actor_user_id = %s
                  and target_id = %s
                  and action = 'client_onboarding.requirements_bypassed'
                """,
                (case.actor_user_id, case.applicant_id),
            ).fetchone()["count"]

        assert onboarding_row["status"] == "under_verification"
        assert onboarding_row["promoted_client_id"] is None
        assert onboarding_row["bypassed_requirements"] == []
        assert onboarding_row["bypass_reason"] is None
        assert onboarding_row["bypassed_by_user_id"] is None
        assert onboarding_row["bypassed_at"] is None
        assert matching_client_count == 0
        assert bypass_audit_count == 0
    finally:
        _delete_case(case)


def test_management_bypass_is_not_used_when_all_four_requirements_already_passed() -> None:
    case = _seed_case()
    try:
        repository = PostgresClientOnboardingRepository()
        record = repository.bypass_and_approve_eligibility(
            actor_user_id=case.actor_user_id,
            applicant_id=case.applicant_id,
            bypassed_requirements=("national_id",),
            reason="Approved exception",
        )

        assert record.status == "under_verification"
        assert record.promoted_client_id is None

        assert DATABASE_URL is not None
        with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
            onboarding_row = connection.execute(
                """
                select status, promoted_client_id, bypassed_requirements
                from lending.client_onboarding_applicants
                where id = %s
                """,
                (case.applicant_id,),
            ).fetchone()
            matching_client_count = connection.execute(
                """
                select count(*) as count
                from lending.clients
                where client_code = %s
                """,
                (case.expected_client_code,),
            ).fetchone()["count"]

        assert onboarding_row["status"] == "under_verification"
        assert onboarding_row["promoted_client_id"] is None
        assert onboarding_row["bypassed_requirements"] == []
        assert matching_client_count == 0
    finally:
        _delete_case(case)
