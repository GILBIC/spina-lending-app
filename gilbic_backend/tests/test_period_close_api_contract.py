from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API = (ROOT / "src" / "gilbic_backend" / "period_close_api.py").read_text(encoding="utf-8")
REPOSITORY = (ROOT / "src" / "gilbic_backend" / "period_close_repository.py").read_text(
    encoding="utf-8"
)
MAIN = (ROOT / "src" / "gilbic_backend" / "main.py").read_text(encoding="utf-8")


def test_period_close_api_is_management_only_strict_and_wired() -> None:
    assert 'model_config = ConfigDict(extra="forbid")' in API
    assert '"management" not in actor.roles' in API
    assert "actor_user_id=actor.user_id" in API
    assert "actor.account_id" not in API
    assert "create_period_close_router" in MAIN
    assert "app.include_router(create_period_close_router())" in MAIN
    assert "/api/mobile/" not in API


def test_period_close_api_requires_action_permissions_and_explicit_confirmation() -> None:
    for permission in (
        'CLOSE_PREPARE_PERMISSION = "accounting.period.close.prepare"',
        'CLOSE_POST_PERMISSION = "accounting.period.close.post"',
    ):
        assert permission in API
    assert API.count("confirm: bool = False") == 2
    assert "_require_confirmation" in API
    assert '"preparing the immutable formal period-close snapshot"' in API
    assert '"posting retained earnings and closing the accounting period"' in API
    assert "Explicit Management confirmation is required before {action}." in API


def test_period_close_api_exposes_exact_close_coordinates_only() -> None:
    for route in (
        '"/api/v1/management/financial-accounting/period-close"',
        '"/api/v1/management/financial-accounting/period-close/{fiscal_period_id}/prepare"',
        '"/api/v1/management/financial-accounting/period-close/{fiscal_period_id}/post"',
    ):
        assert route in API
    for field in (
        "confirmation_token",
        "expected_close_digest",
        "expected_net_income",
        "expected_retained_earnings_account_code",
        "expected_period_end_date",
    ):
        assert field in API
    assert 'Literal["3100"]' in API
    assert 'POLICY = "period_close_retained_earnings_v1"' in REPOSITORY
    assert "exact currency-cent precision" in API
    assert "period_reopen_enabled" in API
    assert "automatic_source_posting" in API


def test_period_close_repository_calls_only_protected_close_functions_and_views() -> None:
    assert "accounting.period_close_queue" in REPOSITORY
    assert "accounting.period_close_summary" in REPOSITORY
    assert "accounting.prepare_period_close" in REPOSITORY
    assert "accounting.post_period_close" in REPOSITORY
    lower = REPOSITORY.lower()
    assert "insert into accounting.journal_entries" not in lower
    assert "insert into accounting.journal_lines" not in lower
    assert "accounting.post_journal_entry" not in REPOSITORY
    assert "accounting.set_fiscal_period_status" not in REPOSITORY


def test_period_close_status_filters_keep_legacy_closed_periods_fail_closed() -> None:
    assert "ready_for_review" in REPOSITORY
    assert "ready_to_prepare" in REPOSITORY
    assert "prepared_confirmation_required" in REPOSITORY
    assert "closed_protected" in REPOSITORY
    assert "closed_legacy_without_protected_close_audit" in REPOSITORY
    assert "close_status LIKE 'blocked_%'" in REPOSITORY
