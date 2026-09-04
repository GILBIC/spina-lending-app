from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID

import psycopg


ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ROOT / "gilbic_backend" / "sql" / "0001_core_lending_foundation.sql"
MIGRATION = (
    ROOT
    / "gilbic_backend"
    / "sql"
    / "0110_add_cif_and_restricted_identity_foundation.sql"
)

PREPARER = UUID("11111111-1111-1111-1111-111111111111")
VERIFIER = UUID("22222222-2222-2222-2222-222222222222")
APPROVER = UUID("33333333-3333-3333-3333-333333333333")
DEVICE = UUID("44444444-4444-4444-4444-444444444444")
CLIENT = UUID("55555555-5555-5555-5555-555555555555")
OTHER_CLIENT = UUID("66666666-6666-6666-6666-666666666666")
CIF = UUID("77777777-7777-7777-7777-777777777777")
SECOND_CIF = UUID("88888888-8888-8888-8888-888888888888")
EVIDENCE = UUID("99999999-9999-9999-9999-999999999999")


def _expect_database_error(connection: psycopg.Connection, sql: str, params: tuple) -> None:
    try:
        connection.execute(sql, params)
    except psycopg.Error:
        return
    raise AssertionError("Expected PostgreSQL to reject the operation")


def _scalar(connection: psycopg.Connection, sql: str, params: tuple = ()):
    return connection.execute(sql, params).fetchone()[0]


def main() -> int:
    if os.getenv("SPINA_DISPOSABLE_DATABASE") != "1":
        raise SystemExit(
            "Refusing to run without SPINA_DISPOSABLE_DATABASE=1"
        )
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("DATABASE_URL is required")

    with psycopg.connect(database_url, autocommit=True) as connection:
        connection.execute(FOUNDATION.read_text(encoding="utf-8"))
        migration_sql = MIGRATION.read_text(encoding="utf-8")
        connection.execute(migration_sql)

        connection.execute(
            """
            insert into core.users (id, username, full_name, status)
            values
                (%s, 'cif_preparer', 'CIF Preparer', 'active'),
                (%s, 'cif_verifier', 'CIF Verifier', 'active'),
                (%s, 'cif_approver', 'CIF Approver', 'active')
            """,
            (PREPARER, VERIFIER, APPROVER),
        )
        connection.execute(
            """
            insert into core.devices (
                id, user_id, device_identifier_hash,
                platform, status
            ) values (%s, %s, %s, 'desktop', 'active')
            """,
            (DEVICE, APPROVER, "d" * 64),
        )
        connection.execute(
            """
            insert into lending.clients (
                id, client_code, full_name, status
            ) values
                (%s, 'CIF-CLIENT-1', 'Maria Dela Cruz', 'active'),
                (%s, 'CIF-CLIENT-2', 'Ana Dela Cruz', 'active')
            """,
            (CLIENT, OTHER_CLIENT),
        )
        connection.execute(
            """
            insert into lending.client_information_forms (
                id, cif_number, client_id, form_version,
                legal_full_name, present_address,
                permanent_address, livelihood_profile,
                privacy_notice_version, privacy_acknowledged_at,
                client_signature_reference,
                client_signature_sha256,
                prepared_by_user_id, form_schema_version
            ) values (
                %s, 'CIF-TEST-0001', %s, 1,
                'Maria Dela Cruz',
                '{"barangay":"San Roque"}'::jsonb,
                '{"barangay":"San Roque"}'::jsonb,
                '{"occupation":"Store owner"}'::jsonb,
                'privacy-v1', '2026-09-04T00:00:00Z',
                'restricted-signature-reference', %s,
                %s, 'cif-v1'
            )
            """,
            (CIF, CLIENT, "a" * 64, PREPARER),
        )
        connection.execute(
            """
            update lending.client_information_forms
            set verified_by_user_id = %s,
                verified_at = '2026-09-04T01:00:00Z',
                content_digest_sha256 = %s
            where id = %s
            """,
            (VERIFIER, "b" * 64, CIF),
        )
        connection.execute(
            """
            update lending.client_information_forms
            set lifecycle_state = 'active',
                effective_at = '2026-09-04T02:00:00Z',
                expires_at = '2031-09-04T02:00:00Z',
                approved_by_user_id = %s,
                approved_at = '2026-09-04T02:00:00Z'
            where id = %s
            """,
            (APPROVER, CIF),
        )

        assert _scalar(
            connection,
            """
            select expires_at = effective_at + interval '5 years'
            from lending.client_information_forms
            where id = %s
            """,
            (CIF,),
        ) is True
        assert _scalar(
            connection,
            """
            select allows_existing_obligation_servicing
            from lending.client_information_form_status
            where id = %s
            """,
            (CIF,),
        ) is True

        _expect_database_error(
            connection,
            """
            update lending.client_information_forms
            set legal_full_name = 'Altered Name'
            where id = %s
            """,
            (CIF,),
        )
        _expect_database_error(
            connection,
            """
            insert into lending.client_information_forms (
                id, cif_number, client_id, form_version,
                lifecycle_state, effective_at, expires_at,
                supersedes_cif_id, legal_full_name,
                present_address, permanent_address,
                livelihood_profile, privacy_notice_version,
                privacy_acknowledged_at,
                client_signature_reference,
                client_signature_sha256,
                prepared_by_user_id, verified_by_user_id,
                verified_at, approved_by_user_id, approved_at,
                content_digest_sha256, form_schema_version
            ) values (
                %s, 'CIF-TEST-CROSS', %s, 1,
                'active', '2026-09-04T03:00:00Z',
                '2031-09-04T03:00:00Z', %s,
                'Ana Dela Cruz', '{}'::jsonb, '{}'::jsonb,
                '{}'::jsonb, 'privacy-v1',
                '2026-09-04T00:00:00Z', 'signature', %s,
                %s, %s, '2026-09-04T01:00:00Z',
                %s, '2026-09-04T03:00:00Z', %s, 'cif-v1'
            )
            """,
            (
                SECOND_CIF,
                OTHER_CLIENT,
                CIF,
                "c" * 64,
                PREPARER,
                VERIFIER,
                APPROVER,
                "d" * 64,
            ),
        )

        connection.execute(
            """
            insert into lending.client_cif_reverification_requirements (
                client_id, source_cif_id, reason,
                severity, opened_by_user_id
            ) values (
                %s, %s, 'address_change', 'standard', %s
            )
            """,
            (CLIENT, CIF, APPROVER),
        )
        assert _scalar(
            connection,
            """
            select is_eligible_for_new_credit
            from lending.client_information_form_status
            where id = %s
            """,
            (CIF,),
        ) is False
        assert _scalar(
            connection,
            """
            select allows_existing_obligation_servicing
            from lending.client_information_form_status
            where id = %s
            """,
            (CIF,),
        ) is True

        connection.execute(
            """
            insert into restricted_identity.cif_verification_evidence (
                id, cif_id, client_id, evidence_type,
                verification_method, verification_result,
                checked_at, masked_reference,
                external_evidence_reference, evidence_sha256,
                retention_class, retain_until,
                verified_by_user_id, created_by_user_id
            ) values (
                %s, %s, %s, 'national_id_check',
                'National ID Check', 'verified',
                '2026-09-04T04:00:00Z', '****1234',
                'restricted/test/evidence', %s,
                'identity_verification', '2031-09-04',
                %s, %s
            )
            """,
            (EVIDENCE, CIF, CLIENT, "e" * 64, VERIFIER, PREPARER),
        )
        connection.execute(
            """
            update restricted_identity.cif_verification_evidence
            set review_state = 'verified',
                final_reviewed_by_user_id = %s,
                reviewed_at = '2026-09-04T05:00:00Z'
            where id = %s
            """,
            (APPROVER, EVIDENCE),
        )
        connection.execute(
            """
            insert into restricted_identity.evidence_access_events (
                evidence_id, cif_id, client_id, actor_user_id,
                registered_device_id, action, purpose_code, request_id
            ) values (
                %s, %s, %s, %s, %s,
                'view', 'compliance_review', %s
            )
            """,
            (
                EVIDENCE,
                CIF,
                CLIENT,
                APPROVER,
                DEVICE,
                UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            ),
        )
        assert _scalar(
            connection,
            """
            select count(*)
            from restricted_identity.evidence_access_events
            where evidence_id = %s
            """,
            (EVIDENCE,),
        ) == 1
        _expect_database_error(
            connection,
            """
            update restricted_identity.cif_verification_evidence
            set masked_reference = 'changed'
            where id = %s
            """,
            (EVIDENCE,),
        )

        forbidden_columns = _scalar(
            connection,
            """
            select count(*)
            from information_schema.columns
            where table_schema = 'restricted_identity'
              and column_name in (
                  'raw_document', 'document_bytes', 'otp', 'mpin',
                  'password', 'atm_pin', 'phone_contacts',
                  'full_national_id', 'provider_payload'
              )
            """,
        )
        assert forbidden_columns == 0

        connection.execute("drop role if exists spina_cif_probe")
        connection.execute("create role spina_cif_probe nologin")
        assert _scalar(
            connection,
            """
            select has_schema_privilege(
                'spina_cif_probe',
                'restricted_identity',
                'USAGE'
            )
            """,
        ) is False
        connection.execute("drop role spina_cif_probe")

        connection.execute(migration_sql)
        assert _scalar(
            connection,
            """
            select count(*)
            from lending.client_information_forms
            where id = %s
            """,
            (CIF,),
        ) == 1

    print("0110 CIF and restricted identity disposable PostgreSQL validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
