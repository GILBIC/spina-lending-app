from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = (
    ROOT
    / "gilbic_backend"
    / "sql"
    / "0110_add_cif_and_restricted_identity_foundation.sql"
)


def _migration() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_creates_versioned_cif_lifecycle() -> None:
    sql = _migration()

    assert "CREATE TABLE IF NOT EXISTS lending.client_information_forms" in sql
    assert "client_id UUID NOT NULL REFERENCES lending.clients(id)" in sql
    assert "UNIQUE (client_id, form_version)" in sql
    assert "supersedes_cif_id UUID" in sql
    assert "lifecycle_state IN ('draft', 'active', 'superseded')" in sql
    assert "effective_at + INTERVAL '5 years'" in sql
    assert "WHERE lifecycle_state = 'active'" in sql
    assert "CREATE VIEW lending.client_information_form_status" in sql
    assert "INTERVAL '90 days'" in sql
    assert "is_eligible_for_new_credit" in sql


def test_migration_adds_reverification_and_immutable_events() -> None:
    sql = _migration()

    assert (
        "CREATE TABLE IF NOT EXISTS lending.client_cif_reverification_requirements"
        in sql
    )
    for reason in (
        "material_identity_change",
        "address_change",
        "contact_change",
        "document_expiry",
        "discrepancy",
        "suspicious_activity",
        "other_risk_event",
    ):
        assert f"'{reason}'" in sql
    assert "CREATE TABLE IF NOT EXISTS lending.client_cif_events" in sql
    assert "guard_client_cif_event_immutability" in sql
    assert "BEFORE UPDATE OR DELETE ON lending.client_cif_events" in sql


def test_migration_creates_private_metadata_only_evidence_boundary() -> None:
    sql = _migration()
    lowered = sql.lower()

    assert "CREATE SCHEMA IF NOT EXISTS restricted_identity" in sql
    assert "REVOKE ALL ON SCHEMA restricted_identity FROM PUBLIC" in sql
    assert (
        "CREATE TABLE IF NOT EXISTS restricted_identity.cif_verification_evidence"
        in sql
    )
    assert (
        "CREATE TABLE IF NOT EXISTS restricted_identity.evidence_access_events"
        in sql
    )
    assert "evidence_sha256 CHAR(64)" in sql
    assert "masked_reference TEXT" in sql
    assert "retention_class TEXT" in sql
    assert "legal_hold BOOLEAN" in sql
    assert "purpose_code TEXT" in sql
    assert "request_id UUID" in sql
    assert "REVOKE ALL ON ALL TABLES IN SCHEMA restricted_identity FROM PUBLIC" in sql

    forbidden_columns = (
        "raw_payload",
        "raw_document",
        "document_bytes",
        "otp",
        "mpin",
        "password",
        "atm_pin",
        "phone_contacts",
        "full_national_id",
    )
    for forbidden in forbidden_columns:
        assert forbidden not in lowered


def test_migration_enforces_same_client_and_immutable_verified_history() -> None:
    sql = _migration()

    assert "guard_cif_supersession_client" in sql
    assert "guard_client_information_form_mutation" in sql
    assert "guard_restricted_evidence_client" in sql
    assert "guard_restricted_evidence_mutation" in sql
    assert "guard_evidence_access_event_immutability" in sql
    assert "verified_by_user_id <> approved_by_user_id" in sql
    assert "final_reviewed_by_user_id <> verified_by_user_id" in sql


def test_migration_adds_narrow_application_permissions() -> None:
    sql = _migration()

    for permission in (
        "cif.view",
        "cif.prepare",
        "cif.verify",
        "cif.approve",
        "cif.reverification.open",
        "identity_evidence.view",
        "identity_evidence.manage",
    ):
        assert f"'{permission}'" in sql

    assert "WHERE role.code IN ('employee', 'management')" in sql
    assert "WHERE role.code = 'management'" in sql
    assert "WHERE role.code IN ('client', 'collector')" not in sql
