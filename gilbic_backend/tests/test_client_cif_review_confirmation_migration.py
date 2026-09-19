from pathlib import Path


SQL_PATH = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0119_add_client_cif_review_confirmation.sql"
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


def test_cif_review_confirmation_declares_append_only_guards() -> None:
    sql = " ".join(SQL_PATH.read_text(encoding="utf-8").lower().split())

    assert "before update or delete on lending.client_cif_review_confirmations" in sql
    assert "before truncate on lending.client_cif_review_confirmations" in sql
    guard = "execute function lending.reject_client_cif_review_confirmation_mutation()"
    assert f"for each row {guard}" in sql
    assert f"for each statement {guard}" in sql
    assert "raise exception 'cif review confirmations are immutable'" in sql
    assert "revoke all on lending.client_cif_review_confirmations from public" in sql
    assert (
        "revoke execute on function lending.reject_client_cif_review_confirmation_mutation() from public"
        in sql
    )
    assert "security definer" not in sql


def test_cif_review_confirmation_binds_client_to_exact_cif_version() -> None:
    sql = " ".join(SQL_PATH.read_text(encoding="utf-8").lower().split())

    assert "on lending.client_cif_versions(id, client_id)" in sql
    assert (
        "foreign key (cif_version_id, client_id) "
        "references lending.client_cif_versions(id, client_id) on delete restrict"
        in sql
    )
    assert "check (jsonb_typeof(review_snapshot) = 'object')" in sql
    assert "check (review_snapshot <> '{}'::jsonb)" in sql
    assert "on delete cascade" not in sql
