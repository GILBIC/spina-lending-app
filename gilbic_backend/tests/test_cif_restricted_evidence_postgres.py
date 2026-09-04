from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest

from gilbic_backend.cif_domain import five_year_expiry


DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="GILBIC_TEST_DATABASE_URL is not configured",
)
ROOT = Path(__file__).parents[2]
SQL_DIR = ROOT / "gilbic_backend" / "sql"


def _apply(connection: psycopg.Connection, filename: str) -> None:
    connection.execute((SQL_DIR / filename).read_text(encoding="utf-8"))


def _counts(connection: psycopg.Connection) -> tuple[int, int, int]:
    return tuple(
        connection.execute(f"select count(*) from {table}").fetchone()[0]
        for table in (
            "lending.clients",
            "lending.loans",
            "core.audit_logs",
        )
    )


@pytest.fixture(scope="module")
def database():
    assert DATABASE_URL is not None
    connection = psycopg.connect(DATABASE_URL, autocommit=True)
    _apply(connection, "0001_core_lending_foundation.sql")
    _apply(connection, "0003_add_management_administration.sql")
    baseline = _counts(connection)
    _apply(connection, "0110_add_client_information_forms_and_restricted_evidence.sql")
    _apply(connection, "0110_add_client_information_forms_and_restricted_evidence.sql")
    try:
        yield connection, baseline
    finally:
        connection.close()


def _insert_user(connection: psycopg.Connection, *, label: str) -> UUID:
    suffix = uuid4().hex
    return connection.execute(
        """
        insert into core.users (username, email, full_name, status)
        values (%s, %s, %s, 'active')
        returning id
        """,
        (
            f"cif-{label}-{suffix}",
            f"cif-{label}-{suffix}@example.com",
            f"CIF {label.title()} {suffix[:6]}",
        ),
    ).fetchone()[0]


def _insert_device(
    connection: psycopg.Connection,
    *,
    user_id: UUID,
    label: str,
) -> UUID:
    return connection.execute(
        """
        insert into core.devices (
            user_id,
            device_identifier_hash,
            platform,
            app_version,
            status
        ) values (%s, %s, 'web', 'cif-test', 'active')
        returning id
        """,
        (user_id, f"cif-device-{label}-{uuid4().hex}"),
    ).fetchone()[0]


def _insert_client(connection: psycopg.Connection, *, label: str) -> UUID:
    suffix = uuid4().hex[:10]
    return connection.execute(
        """
        insert into lending.clients (client_code, full_name, area, status)
        values (%s, %s, 'CIF TEST AREA', 'active')
        returning id
        """,
        (f"CIF-{label.upper()}-{suffix}", f"CIF Client {label} {suffix}"),
    ).fetchone()[0]


def _insert_verified_draft(
    connection: psycopg.Connection,
    *,
    client_id: UUID,
    form_version: int,
    preparer_id: UUID,
    verifier_id: UUID,
    supersedes_cif_id: UUID | None = None,
) -> UUID:
    return connection.execute(
        """
        insert into lending.client_information_forms (
            client_id,
            form_version,
            supersedes_cif_id,
            legal_full_name,
            birth_date,
            place_of_birth,
            nationality,
            civil_status,
            phone_number,
            present_address,
            permanent_address,
            livelihood_profile,
            privacy_notice_version,
            privacy_acknowledged_at,
            client_signature_reference,
            client_signature_digest,
            prepared_by_user_id,
            verified_by_user_id,
            verified_at,
            verification_note,
            source_digest
        ) values (
            %s, %s, %s, 'Synthetic Client', '1990-01-02', 'Rizal',
            'Filipino', 'single', '09170000000',
            '{"line1":"Synthetic present","barangay":"San Juan","province":"Rizal"}'::jsonb,
            '{"line1":"Synthetic permanent","barangay":"San Juan","province":"Rizal"}'::jsonb,
            '{"kind":"self_employed","description":"Synthetic test livelihood"}'::jsonb,
            'privacy-v1', now(), 'restricted-signature://synthetic', %s,
            %s, %s, now(), 'Synthetic verification completed.', %s
        )
        returning id
        """,
        (
            client_id,
            form_version,
            supersedes_cif_id,
            "b" * 64,
            preparer_id,
            verifier_id,
            "a" * 64,
        ),
    ).fetchone()[0]


def _insert_active(
    connection: psycopg.Connection,
    *,
    client_id: UUID,
    form_version: int,
    preparer_id: UUID,
    verifier_id: UUID,
    approver_id: UUID,
    effective_at: datetime,
    expires_at: datetime | None = None,
) -> UUID:
    actual_expiry = expires_at or five_year_expiry(effective_at)
    return connection.execute(
        """
        insert into lending.client_information_forms (
            client_id,
            form_version,
            lifecycle_state,
            effective_at,
            expires_at,
            legal_full_name,
            birth_date,
            place_of_birth,
            nationality,
            civil_status,
            phone_number,
            present_address,
            permanent_address,
            livelihood_profile,
            privacy_notice_version,
            privacy_acknowledged_at,
            client_signature_reference,
            client_signature_digest,
            prepared_by_user_id,
            verified_by_user_id,
            verified_at,
            verification_note,
            approved_by_user_id,
            approved_at,
            approval_note,
            source_digest
        ) values (
            %s, %s, 'active', %s, %s, 'Synthetic Active Client',
            '1991-02-03', 'Rizal', 'Filipino', 'single', '09171111111',
            '{"line1":"Synthetic present","barangay":"San Juan","province":"Rizal"}'::jsonb,
            '{"line1":"Synthetic permanent","barangay":"San Juan","province":"Rizal"}'::jsonb,
            '{"kind":"employed","description":"Synthetic test livelihood"}'::jsonb,
            'privacy-v1', now(), 'restricted-signature://synthetic-active', %s,
            %s, %s, now(), 'Synthetic verification completed.',
            %s, now(), 'Synthetic approval completed.', %s
        )
        returning id
        """,
        (
            client_id,
            form_version,
            effective_at,
            actual_expiry,
            "d" * 64,
            preparer_id,
            verifier_id,
            approver_id,
            "c" * 64,
        ),
    ).fetchone()[0]


def _expect_database_error(connection: psycopg.Connection, operation) -> None:
    with pytest.raises(psycopg.Error):
        with connection.transaction():
            operation()


def test_migration_is_idempotent_additive_and_private(database) -> None:
    connection, baseline = database

    assert _counts(connection) == baseline
    installed = {
        row[0]
        for row in connection.execute(
            """
            select code
            from core.permissions
            where code like 'cif.%' or code like 'identity_evidence.%'
            """
        ).fetchall()
    }
    assert installed == {
        "cif.view",
        "cif.prepare",
        "cif.verify",
        "cif.approve",
        "cif.reverification.manage",
        "identity_evidence.view",
        "identity_evidence.record",
        "identity_evidence.review",
    }

    employee_permissions = {
        row[0]
        for row in connection.execute(
            """
            select role_permission.permission_code
            from core.role_permissions role_permission
            join core.roles role on role.id = role_permission.role_id
            where role.code = 'employee'
              and (
                  role_permission.permission_code like 'cif.%'
                  or role_permission.permission_code like 'identity_evidence.%'
              )
            """
        ).fetchall()
    }
    assert employee_permissions == {"cif.view", "cif.prepare"}

    public_has_restricted_schema_privilege = connection.execute(
        """
        select exists (
            select 1
            from pg_namespace namespace
            cross join lateral aclexplode(
                coalesce(namespace.nspacl, acldefault('n', namespace.nspowner))
            ) privilege
            where namespace.nspname = 'restricted_identity'
              and privilege.grantee = 0
              and privilege.privilege_type in ('USAGE', 'CREATE')
        )
        """
    ).fetchone()[0]
    assert public_has_restricted_schema_privilege is False

    for relation in (
        "lending.client_information_forms",
        "lending.client_cif_reverification_requirements",
        "restricted_identity.cif_verification_evidence",
        "restricted_identity.cif_verification_evidence_reviews",
        "restricted_identity.evidence_access_events",
    ):
        assert connection.execute("select to_regclass(%s)", (relation,)).fetchone()[0]


def test_cif_constraints_status_and_immutability(database) -> None:
    connection, _ = database
    preparer_id = _insert_user(connection, label="preparer")
    verifier_id = _insert_user(connection, label="verifier")
    approver_id = _insert_user(connection, label="approver")
    client_id = _insert_client(connection, label="lifecycle")
    other_client_id = _insert_client(connection, label="other")

    cif_v1 = _insert_verified_draft(
        connection,
        client_id=client_id,
        form_version=1,
        preparer_id=preparer_id,
        verifier_id=verifier_id,
    )
    effective_v1 = datetime.now(UTC).replace(microsecond=0)
    expires_v1 = five_year_expiry(effective_v1)
    connection.execute(
        """
        update lending.client_information_forms
        set lifecycle_state = 'active',
            effective_at = %s,
            expires_at = %s,
            approved_by_user_id = %s,
            approved_at = now(),
            approval_note = 'Synthetic activation approved.'
        where id = %s
        """,
        (effective_v1, expires_v1, approver_id, cif_v1),
    )
    status = connection.execute(
        """
        select public_status, is_eligible_for_new_credit
        from lending.client_information_form_status
        where id = %s
        """,
        (cif_v1,),
    ).fetchone()
    assert status == ("Active", True)

    requirement_id = connection.execute(
        """
        insert into lending.client_cif_reverification_requirements (
            client_id,
            source_cif_id,
            reason,
            severity,
            note,
            opened_by_user_id
        ) values (
            %s, %s, 'address_change', 'standard',
            'Synthetic address change requires re-verification.', %s
        )
        returning id
        """,
        (client_id, cif_v1, approver_id),
    ).fetchone()[0]
    assert connection.execute(
        """
        select is_eligible_for_new_credit
        from lending.client_information_form_status
        where id = %s
        """,
        (cif_v1,),
    ).fetchone()[0] is False

    cif_v2 = _insert_verified_draft(
        connection,
        client_id=client_id,
        form_version=2,
        preparer_id=preparer_id,
        verifier_id=verifier_id,
        supersedes_cif_id=cif_v1,
    )

    _expect_database_error(
        connection,
        lambda: _insert_verified_draft(
            connection,
            client_id=client_id,
            form_version=3,
            preparer_id=preparer_id,
            verifier_id=verifier_id,
            supersedes_cif_id=cif_v1,
        ),
    )
    _expect_database_error(
        connection,
        lambda: _insert_verified_draft(
            connection,
            client_id=other_client_id,
            form_version=1,
            preparer_id=preparer_id,
            verifier_id=verifier_id,
            supersedes_cif_id=cif_v1,
        ),
    )

    effective_v2 = effective_v1 + timedelta(seconds=1)
    expires_v2 = five_year_expiry(effective_v2)
    with connection.transaction():
        connection.execute(
            """
            update lending.client_information_forms
            set lifecycle_state = 'superseded'
            where id = %s
            """,
            (cif_v1,),
        )
        connection.execute(
            """
            update lending.client_information_forms
            set lifecycle_state = 'active',
                effective_at = %s,
                expires_at = %s,
                approved_by_user_id = %s,
                approved_at = now(),
                approval_note = 'Synthetic replacement approved.'
            where id = %s
            """,
            (effective_v2, expires_v2, approver_id, cif_v2),
        )
        connection.execute(
            """
            update lending.client_cif_reverification_requirements
            set status = 'resolved',
                resolved_by_user_id = %s,
                resolved_at = now(),
                resolution_cif_id = %s,
                resolution_note = 'Resolved by synthetic replacement CIF.'
            where id = %s
            """,
            (approver_id, cif_v2, requirement_id),
        )

    statuses = dict(
        connection.execute(
            """
            select id, public_status
            from lending.client_information_form_status
            where id in (%s, %s)
            """,
            (cif_v1, cif_v2),
        ).fetchall()
    )
    assert statuses == {cif_v1: "Superseded", cif_v2: "Active"}

    _expect_database_error(
        connection,
        lambda: connection.execute(
            "update lending.client_information_forms set legal_full_name = 'Changed' where id = %s",
            (cif_v2,),
        ),
    )
    _expect_database_error(
        connection,
        lambda: connection.execute(
            "delete from lending.client_information_forms where id = %s",
            (cif_v2,),
        ),
    )
    _expect_database_error(
        connection,
        lambda: connection.execute(
            "update lending.client_cif_reverification_requirements set note = 'Changed' where id = %s",
            (requirement_id,),
        ),
    )
    _expect_database_error(
        connection,
        lambda: _insert_active(
            connection,
            client_id=client_id,
            form_version=3,
            preparer_id=preparer_id,
            verifier_id=verifier_id,
            approver_id=approver_id,
            effective_at=effective_v2,
        ),
    )
    _expect_database_error(
        connection,
        lambda: _insert_active(
            connection,
            client_id=other_client_id,
            form_version=1,
            preparer_id=preparer_id,
            verifier_id=verifier_id,
            approver_id=approver_id,
            effective_at=effective_v2,
            expires_at=effective_v2 + timedelta(days=365),
        ),
    )

    expiring_client_id = _insert_client(connection, label="expiring")
    expired_client_id = _insert_client(connection, label="expired")
    expiring_effective = datetime.now(UTC) - timedelta(days=(365 * 5) - 30)
    expired_effective = datetime.now(UTC) - timedelta(days=(365 * 5) + 10)
    expiring_cif = _insert_active(
        connection,
        client_id=expiring_client_id,
        form_version=1,
        preparer_id=preparer_id,
        verifier_id=verifier_id,
        approver_id=approver_id,
        effective_at=expiring_effective,
    )
    expired_cif = _insert_active(
        connection,
        client_id=expired_client_id,
        form_version=1,
        preparer_id=preparer_id,
        verifier_id=verifier_id,
        approver_id=approver_id,
        effective_at=expired_effective,
    )
    time_statuses = dict(
        connection.execute(
            """
            select id, public_status
            from lending.client_information_form_status
            where id in (%s, %s)
            """,
            (expiring_cif, expired_cif),
        ).fetchall()
    )
    assert time_statuses == {expiring_cif: "Expiring", expired_cif: "Expired"}

    assert connection.execute(
        "select count(*) from lending.loans where client_id in (%s, %s, %s, %s)",
        (client_id, other_client_id, expiring_client_id, expired_client_id),
    ).fetchone()[0] == 0
    assert connection.execute(
        "select count(*) from lending.collection_transactions where client_id in (%s, %s, %s, %s)",
        (client_id, other_client_id, expiring_client_id, expired_client_id),
    ).fetchone()[0] == 0


def test_restricted_evidence_is_append_only_reviewed_and_access_logged(database) -> None:
    connection, _ = database
    recorder_id = _insert_user(connection, label="evidence-recorder")
    reviewer_id = _insert_user(connection, label="evidence-reviewer")
    recorder_device_id = _insert_device(
        connection,
        user_id=recorder_id,
        label="recorder",
    )
    reviewer_device_id = _insert_device(
        connection,
        user_id=reviewer_id,
        label="reviewer",
    )
    client_id = _insert_client(connection, label="evidence")
    other_client_id = _insert_client(connection, label="evidence-other")
    effective_at = datetime.now(UTC).replace(microsecond=0)
    cif_id = _insert_active(
        connection,
        client_id=client_id,
        form_version=1,
        preparer_id=recorder_id,
        verifier_id=recorder_id,
        approver_id=reviewer_id,
        effective_at=effective_at,
    )

    evidence_id = connection.execute(
        """
        insert into restricted_identity.cif_verification_evidence (
            client_id,
            cif_id,
            evidence_type,
            verification_method,
            verification_outcome,
            checked_at,
            document_date,
            document_expires_at,
            masked_reference,
            external_evidence_reference,
            evidence_digest,
            retention_class,
            retain_until,
            recorded_by_user_id
        ) values (
            %s, %s, 'national_id_check', 'approved-test-adapter', 'verified',
            now(), current_date, current_date + 365,
            '****-****-1234', 'restricted://synthetic/evidence', %s,
            'identity_verification', current_date + 3650, %s
        )
        returning id
        """,
        (client_id, cif_id, "e" * 64, recorder_id),
    ).fetchone()[0]

    _expect_database_error(
        connection,
        lambda: connection.execute(
            """
            insert into restricted_identity.cif_verification_evidence (
                client_id, cif_id, evidence_type, verification_method,
                verification_outcome, checked_at, masked_reference,
                external_evidence_reference, evidence_digest, retention_class,
                retain_until, recorded_by_user_id
            ) values (
                %s, %s, 'utility_proof', 'approved-test-adapter', 'verified',
                now(), '****-4321', 'restricted://synthetic/mismatch', %s,
                'residence_verification', current_date + 3650, %s
            )
            """,
            (other_client_id, cif_id, "f" * 64, recorder_id),
        ),
    )
    _expect_database_error(
        connection,
        lambda: connection.execute(
            "update restricted_identity.cif_verification_evidence set legal_hold = true where id = %s",
            (evidence_id,),
        ),
    )
    _expect_database_error(
        connection,
        lambda: connection.execute(
            "delete from restricted_identity.cif_verification_evidence where id = %s",
            (evidence_id,),
        ),
    )
    _expect_database_error(
        connection,
        lambda: connection.execute(
            """
            insert into restricted_identity.cif_verification_evidence_reviews (
                evidence_id, review_decision, review_note, reviewed_by_user_id
            ) values (%s, 'approved', 'Self review is forbidden.', %s)
            """,
            (evidence_id, recorder_id),
        ),
    )

    review_id = connection.execute(
        """
        insert into restricted_identity.cif_verification_evidence_reviews (
            evidence_id, review_decision, review_note, reviewed_by_user_id
        ) values (%s, 'approved', 'Synthetic independent review completed.', %s)
        returning id
        """,
        (evidence_id, reviewer_id),
    ).fetchone()[0]
    _expect_database_error(
        connection,
        lambda: connection.execute(
            "update restricted_identity.cif_verification_evidence_reviews set review_note = 'Changed' where id = %s",
            (review_id,),
        ),
    )

    request_id = uuid4()
    access_id = connection.execute(
        """
        insert into restricted_identity.evidence_access_events (
            actor_user_id,
            evidence_id,
            action,
            purpose_code,
            registered_device_id,
            request_id
        ) values (%s, %s, 'view', 'compliance_review', %s, %s)
        returning id
        """,
        (reviewer_id, evidence_id, reviewer_device_id, request_id),
    ).fetchone()[0]
    _expect_database_error(
        connection,
        lambda: connection.execute(
            """
            insert into restricted_identity.evidence_access_events (
                actor_user_id, evidence_id, action, purpose_code,
                registered_device_id, request_id
            ) values (%s, %s, 'view', 'dpo_audit', %s, %s)
            """,
            (recorder_id, evidence_id, reviewer_device_id, uuid4()),
        ),
    )
    _expect_database_error(
        connection,
        lambda: connection.execute(
            "update restricted_identity.evidence_access_events set purpose_code = 'dpo_audit' where id = %s",
            (access_id,),
        ),
    )
    _expect_database_error(
        connection,
        lambda: connection.execute(
            "delete from restricted_identity.evidence_access_events where id = %s",
            (access_id,),
        ),
    )

    evidence_status = connection.execute(
        """
        select review_decision, reviewed_by_user_id, is_superseded
        from restricted_identity.cif_verification_evidence_status
        where id = %s
        """,
        (evidence_id,),
    ).fetchone()
    assert evidence_status == ("approved", reviewer_id, False)
    assert recorder_device_id != reviewer_device_id
