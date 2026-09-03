from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = (ROOT / ".github" / "workflows" / "spina-ci.yml").read_text(
    encoding="utf-8"
)
LOWER = WORKFLOW.lower()


def test_unified_ci_keeps_exact_pr_validation_reuse_fail_closed() -> None:
    assert "tools\\reuse_validated_pr_ci.py" in WORKFLOW
    assert "Prove exact successful PR validation" in WORKFLOW
    assert "steps.validated_pr.outputs.reuse_validation != 'true'" in WORKFLOW
    assert "Run backend and database tests" in WORKFLOW
    assert "Run Flutter tests" in WORKFLOW
    assert (
        "Financial/database validation is owned by the separate "
        "SPINA Financial and Database workflow."
    ) in WORKFLOW


def test_completed_financial_live_verifiers_are_not_automatic_main_push_steps() -> None:
    # The tools remain compilable historical utilities, but Core CI must not invoke
    # their live migration commands. Protected live maintenance stays separately gated.
    for step_name in (
        "Protected opening-balance journal draft verification",
        "Protected opening-balance journal posting verification",
        "Protected cutover EIR snapshot verification",
        "Protected Regular journal draft verification",
        "Install Financial Accounting verifier dependencies",
        "Compile Financial Accounting live verifiers",
    ):
        assert step_name not in WORKFLOW

    for marker in (
        "accounting-opening-journal-draft-live-migration.once",
        "accounting-opening-journal-posting-live-migration.once",
        "accounting-cutover-eir-snapshot-live-migration.once",
        "accounting-regular-journal-draft-live-migration.once",
    ):
        assert marker not in WORKFLOW


def test_legacy_stage5e_live_maintenance_stays_explicitly_manual() -> None:
    assert "run_legacy_live_migrations:" in WORKFLOW
    for step_name in (
        "Manual Stage 5E.2 live historical import",
        "Manual Stage 5E.3 live outcome-review migration",
        "Manual Stage 5E.4.1 live contractual DPD migration",
        "Manual Stage 5E.4.3 live verified contract registration migration",
        "Manual Stage 5E.4.6A live per-loan activation schema migration",
    ):
        assert step_name in WORKFLOW
    assert LOWER.count("github.event_name == 'workflow_dispatch' && inputs.run_legacy_live_migrations") == 5


def test_unified_ci_has_no_automatic_live_database_env_dependency() -> None:
    # Main push validation must not depend on local SPINA-WINDOWS env files after an
    # exact PR suite has already passed. Those paths remain only inside manual Stage5E.
    push_sections = []
    for block in WORKFLOW.split("\n      - name: "):
        if "if: github.event_name == 'push'" in block:
            push_sections.append(block)
    joined = "\n".join(push_sections).lower()
    assert "--database-url-env gilbic_database_url" not in joined
    assert "c:\\github\\spina-lending-app-clean\\.env" not in joined
    assert "c:\\spina_online\\spina_backend\\.env" not in joined
