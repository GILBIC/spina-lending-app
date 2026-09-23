from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
import run_stage5d17_disposable_postgres_validation as disposable
from psycopg import sql


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "gilbic_backend" / "src"
TARGET_TEST = (
    ROOT / "gilbic_backend" / "tests" / "test_client_onboarding_promotion_postgres.py"
)
CIF_TEST = (
    ROOT
    / "gilbic_backend"
    / "tests"
    / "test_client_cif_review_confirmation_postgres.py"
)
CIF_CORRECTION_AVAILABILITY_TEST = (
    ROOT
    / "gilbic_backend"
    / "tests"
    / "test_client_cif_correction_availability_postgres.py"
)
ONBOARDING_CIF_SELECTION_TEST = (
    ROOT
    / "gilbic_backend"
    / "tests"
    / "test_client_onboarding_cif_selection_postgres.py"
)
CIF_CONFIRMATION_REPOSITORY_TEST = (
    ROOT
    / "gilbic_backend"
    / "tests"
    / "test_client_cif_review_confirmation_repository_postgres.py"
)
CIF_LOAN_SOURCE_TEST = (
    ROOT / "gilbic_backend" / "tests" / "test_client_cif_active_loan_source_postgres.py"
)
APPLICATION_HISTORY_TEST = (
    ROOT / "gilbic_backend" / "tests" / "test_loan_application_history_postgres.py"
)
APPLICATION_REPOSITORY_TEST = (
    ROOT / "gilbic_backend" / "tests" / "test_loan_application_repository_postgres.py"
)
APPLICATION_REFERENCE_REVIEW_TEST = (
    ROOT
    / "gilbic_backend"
    / "tests"
    / "test_loan_application_reference_review_postgres.py"
)
APPLICATION_ENTRY_CONTEXT_TEST = (
    ROOT
    / "gilbic_backend"
    / "tests"
    / "test_loan_application_entry_context_postgres.py"
)
APPLICATION_CONFIRMATION_TEST = (
    ROOT
    / "gilbic_backend"
    / "tests"
    / "test_loan_application_review_confirmation_postgres.py"
)
CIF_MIGRATIONS = (
    ROOT / "gilbic_backend" / "sql" / "0113_add_authoritative_area_management.sql",
    ROOT / "gilbic_backend" / "sql" / "0114_add_client_cif_first_loan_foundation.sql",
    ROOT
    / "gilbic_backend"
    / "sql"
    / "0115_align_7x7_signed_schedule_accounting_authority.sql",
    ROOT / "gilbic_backend" / "sql" / "0116_enforce_one_active_7x7_per_client.sql",
    ROOT / "gilbic_backend" / "sql" / "0117_add_7x7_pricing_compliance_readiness.sql",
    ROOT
    / "gilbic_backend"
    / "sql"
    / "0118_add_7x7_post_maturity_penalty_authority.sql",
    ROOT / "gilbic_backend" / "sql" / "0119_add_client_cif_review_confirmation.sql",
    ROOT / "gilbic_backend" / "sql" / "0120_add_loan_application_history.sql",
    ROOT
    / "gilbic_backend"
    / "sql"
    / "0121_add_loan_application_review_confirmation.sql",
    ROOT / "gilbic_backend" / "sql" / "0122_add_office_review_evidence.sql",
    ROOT / "gilbic_backend" / "sql" / "0123_add_first_loan_office_release.sql",
    ROOT / "gilbic_backend" / "sql" / "0124_add_loan_application_details.sql",
    ROOT / "gilbic_backend" / "sql" / "0125_add_versioned_privacy_acknowledgments.sql",
    ROOT / "gilbic_backend" / "sql" / "0126_guard_new_credit_with_current_cif.sql",
    ROOT / "gilbic_backend" / "sql" / "0127_add_client_payment_proof_evidence.sql",
    ROOT / "gilbic_backend" / "sql" / "0128_add_employee_operations.sql",
    ROOT / "gilbic_backend" / "sql" / "0129_add_first_loan_disclosure_source.sql",
)
FULL_FLOW_TESTS = tuple(
    ROOT / "gilbic_backend" / "tests" / name
    for name in (
        "test_client_onboarding_case_postgres.py",
        "test_loan_application_extended_postgres.py",
        "test_office_review_evidence_postgres.py",
        "test_first_loan_postgres.py",
        "test_first_loan_disclosure_postgres.py",
        "test_first_loan_disclosure_register_postgres.py",
        "test_first_loan_disclosure_repository_postgres.py",
        "test_first_loan_disclosure_binding_postgres.py",
        "test_first_loan_credentials_postgres.py",
        "test_privacy_records_postgres.py",
        "test_client_cif_lending_guard_postgres.py",
        "test_client_document_postgres.py",
        "test_client_payment_proof_postgres.py",
        "test_employee_authorization_postgres.py",
        "test_employee_operations_postgres.py",
        "test_employee_operations_concurrency_postgres.py",
    )
)
BOOTSTRAP_THROUGH = 112
DISPOSABLE_DATABASE_PREFIX = "spina_onboarding_"


def _test_environment(database_url: str) -> dict[str, str]:
    env = os.environ.copy()
    for key in disposable.ENDPOINT_ENV_KEYS:
        env.pop(key, None)
    env["GILBIC_DATABASE_URL"] = database_url
    env["GILBIC_TEST_DATABASE_URL"] = database_url
    roots = [str(ROOT), str(BACKEND_SRC)]
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join(roots + ([existing] if existing else []))
    return env


def validate(base_database_url: str) -> None:
    if os.getenv("SPINA_ALLOW_DISPOSABLE_DATABASE") != "1":
        raise RuntimeError(
            "Onboarding disposable validation requires SPINA_ALLOW_DISPOSABLE_DATABASE=1."
        )
    for path in (
        TARGET_TEST,
        ONBOARDING_CIF_SELECTION_TEST,
        CIF_TEST,
        CIF_CORRECTION_AVAILABILITY_TEST,
        CIF_CONFIRMATION_REPOSITORY_TEST,
        CIF_LOAN_SOURCE_TEST,
        APPLICATION_HISTORY_TEST,
        APPLICATION_REPOSITORY_TEST,
        APPLICATION_REFERENCE_REVIEW_TEST,
        APPLICATION_ENTRY_CONTEXT_TEST,
        APPLICATION_CONFIRMATION_TEST,
        *FULL_FLOW_TESTS,
        *CIF_MIGRATIONS,
    ):
        if not path.is_file():
            raise RuntimeError(f"Required onboarding/CIF proof file is missing: {path}")

    base_params = disposable._safe_local_connection_params(base_database_url)
    admin_url = disposable._conninfo_for_database(base_params, "postgres")
    database_name = f"{DISPOSABLE_DATABASE_PREFIX}{uuid4().hex[:12]}"
    test_url = disposable._conninfo_for_database(base_params, database_name)
    original_bootstrap_through = disposable.BOOTSTRAP_THROUGH
    created = False

    print(f"Creating onboarding disposable PostgreSQL database: {database_name}")
    try:
        with psycopg.connect(admin_url, autocommit=True) as admin:
            admin.execute(
                sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(
                    sql.Identifier(database_name)
                )
            )
        created = True

        disposable.BOOTSTRAP_THROUGH = BOOTSTRAP_THROUGH
        disposable._install_supabase_auth_prerequisite(test_url)
        disposable._bootstrap_database(test_url)
        # Replay the CIF/application/release prerequisites in one disposable proof.
        with psycopg.connect(test_url, autocommit=True) as connection:
            for path in CIF_MIGRATIONS:
                connection.execute(path.read_text(encoding="utf-8"))

        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                str(TARGET_TEST),
                str(ONBOARDING_CIF_SELECTION_TEST),
                str(CIF_TEST),
                str(CIF_CORRECTION_AVAILABILITY_TEST),
                str(CIF_CONFIRMATION_REPOSITORY_TEST),
                str(CIF_LOAN_SOURCE_TEST),
                str(APPLICATION_HISTORY_TEST),
                str(APPLICATION_REPOSITORY_TEST),
                str(APPLICATION_REFERENCE_REVIEW_TEST),
                str(APPLICATION_ENTRY_CONTEXT_TEST),
                str(APPLICATION_CONFIRMATION_TEST),
                *(str(path) for path in FULL_FLOW_TESTS),
            ],
            cwd=ROOT,
            env=_test_environment(test_url),
            text=True,
            check=False,
            timeout=600,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                "Onboarding disposable PostgreSQL validation failed: "
                f"test exited with code {completed.returncode}."
            )
    finally:
        disposable.BOOTSTRAP_THROUGH = original_bootstrap_through
        if created:
            print(
                f"Dropping onboarding disposable PostgreSQL database: {database_name}"
            )
            with psycopg.connect(admin_url, autocommit=True) as admin:
                disposable._drop_database(admin, database_name)

    print(
        "Onboarding/CIF disposable PostgreSQL validation passed: schema through 0112 "
        "plus Area/CIF/application/release/Client/employee/disclosure migrations 0113 through 0129 was replayed in a fresh loopback database; "
        "confirmation/application-history integrity, immutability and rerun tests passed; normal/bypass promotion "
        "proved exactly-one inactive Client identity, idempotency, preserved bypass "
        "requirement states, and zero new Auth-user or loan side effects."
    )
