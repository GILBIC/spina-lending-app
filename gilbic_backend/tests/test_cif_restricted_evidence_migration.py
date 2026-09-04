from __future__ import annotations

import re
from pathlib import Path


SQL_DIR = Path(__file__).parents[1] / "sql"
MIGRATION_PATH = SQL_DIR / "0110_add_client_information_forms_and_restricted_evidence.sql"


def _migration() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_adds_exact_cif_and_restricted_permissions() -> None:
    sql = _migration().lower()

    for permission in (
        "cif.view",
        "cif.prepare",
        "cif.verify",
        "cif.approve",
        "cif.reverification.manage",
        "identity_evidence.view",
        "identity_evidence.record",
        "identity_evidence.review",
    ):
        assert f"'{permission}'" in sql

    assert "('employee', 'cif.view')" in sql
    assert "('employee', 'cif.prepare')" in sql
    for permission in (
        "cif.view",
        "cif.prepare",
        "cif.verify",
        "cif.approve",
        "cif.reverification.manage",
        "identity_evidence.view",
        "identity_evidence.record",
        "identity_evidence.review",
    ):
        assert f"('management', '{permission}')" in sql


def test_migration_creates_versioned_cif_and_derived_status_projection() -> None:
    sql = _migration().lower()

    assert "create table if not exists lending.client_information_forms" in sql
    assert "create table if not exists lending.client_cif_reverification_requirements" in sql
    assert "create or replace view lending.client_information_form_status" in sql
    assert "lifecycle_state in ('draft', 'active', 'superseded')" in sql
    assert "interval '90 days'" in sql
    assert "interval '5 years'" in sql
    assert "is_eligible_for_new_credit" in sql
    assert "unique (client_id, form_version)" in sql
    assert "where lifecycle_state = 'active'" in sql
    assert "where lifecycle_state = 'draft'" in sql
    assert "supersedes_cif_id" in sql
    assert "verified_by_user_id" in sql
    assert "approved_by_user_id" in sql
    assert "source_digest" in sql


def test_migration_keeps_restricted_evidence_in_a_private_append_only_schema() -> None:
    sql = _migration().lower()

    assert "create schema if not exists restricted_identity" in sql
    assert "revoke all on schema restricted_identity from public" in sql
    assert "alter default privileges in schema restricted_identity revoke all on tables from public" in sql
    assert "alter default privileges in schema restricted_identity revoke all on sequences from public" in sql
    assert "create table if not exists restricted_identity.cif_verification_evidence" in sql
    assert "create table if not exists restricted_identity.cif_verification_evidence_reviews" in sql
    assert "create table if not exists restricted_identity.evidence_access_events" in sql
    assert "create or replace view restricted_identity.cif_verification_evidence_status" in sql
    assert "registered_device_id" in sql
    assert "purpose_code" in sql
    assert "request_id" in sql
    assert "retain_until" in sql
    assert "legal_hold" in sql
    assert "external_evidence_reference" in sql
    assert "evidence_digest" in sql

    assert "grant usage on schema restricted_identity to anon" not in sql
    assert "grant usage on schema restricted_identity to authenticated" not in sql
    assert "grant all on schema restricted_identity" not in sql


def test_migration_rejects_sensitive_or_arbitrary_evidence_columns() -> None:
    sql = _migration().lower()
    evidence_table = sql.split(
        "create table if not exists restricted_identity.cif_verification_evidence",
        1,
    )[1].split("create table if not exists", 1)[0]

    forbidden_column_patterns = (
        r"\braw_content\s+",
        r"\braw_document\s+",
        r"\bpassword\s+",
        r"\botp\s+",
        r"\bmpin\s+",
        r"\batm_details\s+",
        r"\bphone_contacts\s+",
        r"\bcontact_list\s+",
        r"\bnational_id_number\s+",
        r"\bprovider_payload\s+",
        r"\barbitrary_metadata\s+",
    )
    for pattern in forbidden_column_patterns:
        assert re.search(pattern, evidence_table) is None

    assert "masked_reference" in evidence_table
    assert "!~ '[0-9]{6,}'" in evidence_table


def test_migration_installs_immutable_and_cross_client_guards() -> None:
    sql = _migration().lower()

    for function_name in (
        "guard_client_information_form",
        "guard_cif_reverification_requirement",
        "guard_restricted_evidence",
        "guard_restricted_evidence_review",
        "guard_restricted_evidence_access_event",
    ):
        assert f"create or replace function" in sql
        assert function_name in sql

    assert "cif records cannot be deleted" in sql
    assert "activated cif content is immutable" in sql
    assert "restricted evidence records are append-only" in sql
    assert "restricted evidence reviews are append-only" in sql
    assert "restricted evidence access events are append-only" in sql
    assert "superseded cif must belong to the same client" in sql
    assert "superseded evidence must belong to the same client and cif" in sql


def test_every_security_definer_function_pins_search_path() -> None:
    sql = _migration().lower()

    functions = sql.split("create or replace function")[1:]
    assert functions
    for function in functions:
        header = function.split("$$", 1)[0]
        assert "set search_path" in header
