from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SQL = (ROOT / "sql" / "0073_add_ecl_forward_looking_evidence_governance.sql").read_text(
    encoding="utf-8"
)
DOC = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "accounting"
    / "ecl-forward-looking-evidence-governance.md"
).read_text(encoding="utf-8")


def test_0073_defines_versioned_authoritative_forward_looking_evidence() -> None:
    normalized = SQL.upper()
    assert SQL.strip().startswith("BEGIN;")
    assert SQL.strip().endswith("COMMIT;")
    assert "CREATE TABLE IF NOT EXISTS ACCOUNTING.ECL_FORWARD_LOOKING_EVIDENCE" in normalized
    for field in (
        "source_name",
        "source_reference",
        "observation_period_start",
        "observation_period_end",
        "forecast_period_start",
        "forecast_period_end",
        "retrieved_at",
        "effective_date",
        "management_interpretation",
        "approved_by_user_id",
        "approved_at",
        "supersedes_evidence_id",
    ):
        assert field in SQL
    assert "UNIQUE (evidence_key, version)" in SQL
    assert "REFERENCES core.users(id) ON DELETE RESTRICT" in SQL


def test_0073_requires_protected_management_insert_and_immutable_versions() -> None:
    normalized = SQL.upper()
    assert "ACCOUNTING.ECL.FORWARD_LOOKING_EVIDENCE.MANAGE" in normalized
    assert "WHERE ROLE.CODE = 'MANAGEMENT'" in normalized
    assert "GUARD_ECL_FORWARD_LOOKING_EVIDENCE_WRITE" in normalized
    assert "BEFORE INSERT OR UPDATE OR DELETE" in normalized
    assert "RECORD_ECL_FORWARD_LOOKING_EVIDENCE" in normalized
    assert "EXPLICIT SUPERSEDES_EVIDENCE_ID" in normalized
    assert "PRIOR.VERSION + 1" in normalized
    assert "HAS ALREADY BEEN SUPERSEDED" in normalized


def test_0073_uses_separate_immutable_revocation_evidence() -> None:
    normalized = SQL.upper()
    assert "CREATE TABLE IF NOT EXISTS ACCOUNTING.ECL_FORWARD_LOOKING_EVIDENCE_REVOCATIONS" in normalized
    assert "GUARD_ECL_FORWARD_LOOKING_EVIDENCE_REVOCATION_WRITE" in normalized
    assert "REVOKE_ECL_FORWARD_LOOKING_EVIDENCE" in normalized
    assert "EVIDENCE_ID UUID NOT NULL UNIQUE" in normalized
    assert "REVOKED_BY_USER_ID UUID NOT NULL" in normalized


def test_0073_defines_current_stale_superseded_and_revoked_behavior() -> None:
    for status in ("revoked", "superseded", "not_yet_effective", "stale", "current"):
        assert f"'{status}'" in SQL
    assert "ready_for_new_measurement" in SQL
    assert "current_date >= evidence.effective_date" in SQL
    assert "current_date <= evidence.forecast_period_end" in SQL
    assert "prior measurements retain their exact evidence IDs/versions" in SQL
    assert "later forecast" in DOC.lower()
    assert "must never rewrite" in DOC.lower()


def test_0073_does_not_invent_quantitative_assumptions_or_enable_posting() -> None:
    lower = SQL.lower()
    assert "false AS scenario_probability_defaulted" in SQL
    assert "false AS multiplier_defaulted" in SQL
    assert "false AS management_overlay_defaulted" in SQL
    assert "false AS ecl_calculation_enabled" in SQL
    assert "false AS account_1190_posting_enabled" in SQL
    assert "false AS automatic_source_posting" in SQL
    assert "insert into accounting.journal_entries" not in lower
    assert "insert into accounting.journal_lines" not in lower
    assert "No scenario probability, multiplier or overlay is invented or defaulted" in SQL
    assert "must not invent or default any scenario probability" in DOC
