from pathlib import Path


SQL_PATH = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0115_add_client_cif_review_confirmation.sql"
)


def test_cif_review_confirmation_schema_is_append_only_and_separate_from_loan_release() -> None:
    sql = SQL_PATH.read_text(encoding="utf-8").lower()

    assert "create table if not exists lending.client_cif_review_confirmations" in sql
    assert "client_id uuid not null references lending.clients(id)" in sql
    assert (
        "cif_version_id uuid not null references lending.client_cif_versions(id)" in sql
    )
    assert "review_cycle_number integer not null" in sql
    assert "check (review_cycle_number > 0)" in sql
    assert "unique (client_id, review_cycle_number)" in sql
    assert "unique (cif_version_id)" in sql

    assert "review_snapshot jsonb not null" in sql
    assert "applicant_confirmation_evidence_reference text not null" in sql
    assert "witnessed_by_user_id uuid not null references core.users(id)" in sql
    assert "confirmed_at timestamptz not null default now()" in sql
    assert "btrim(applicant_confirmation_evidence_reference) <> ''" in sql

    # Applicant review confirmation is evidence of reviewed information only.
    # It must not become a second loan approval/release/authentication state machine.
    for forbidden in (
        "loan_id",
        "approved_at",
        "released_at",
        "auth_user_id",
        "password",
        "schedule_id",
        "journal_id",
    ):
        assert forbidden not in sql
