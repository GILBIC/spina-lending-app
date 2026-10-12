"""Accounting runners must include their renamed dependency migrations."""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "runner,migration",
    [
        ("adapters_disposable", "compose_accounting_source_controls"),
        ("current_schema", "compose_proven_source_assessments"),
        ("transfer_review", "add_retained_period_review_manifests"),
        ("lending", "add_loan_payout_accounting"),
        ("regular_application", "add_regular_treasury_applications"),
        ("native_origin", "add_native_regular_origins"),
        ("collector_application", "add_collector_credit_applications"),
        ("disclosure", "add_journal_disclosure_reviews"),
    ],
)
def test_accounting_validator_contains_its_named_schema(runner, migration):
    path = ROOT / "tools" / f"run_accounting_{runner}_validation.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    values = [
        keyword.value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        for keyword in node.keywords
        if keyword.arg == "bootstrap_through"
        and isinstance(keyword.value, ast.Constant)
    ]
    assert len(values) == 1
    migrations = list((ROOT / "gilbic_backend/sql").glob(f"*_{migration}.sql"))
    assert len(migrations) == 1
    assert values[0] >= int(migrations[0].name[:4])
    # Current Office, tax recovery and private photo migrations precede the new
    # accounting book. A renamed accounting boundary must preserve all three.
    assert values[0] >= 144


def test_historical_accounting_cycle_remains_bounded_to_0092():
    tree = ast.parse(
        (
            ROOT / "tools/run_accounting_cycle_disposable_postgres_validation.py"
        ).read_text(encoding="utf-8")
    )
    assert any(
        isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "BOOTSTRAP_THROUGH"
            for target in node.targets
        )
        and isinstance(node.value, ast.Constant)
        and node.value.value == 92
        for node in tree.body
    )


def test_current_bootstrap_preserves_reserved_gap_and_duplicate_history(
    monkeypatch, tmp_path
):
    import run_stage5d17_disposable_postgres_validation as runner

    for number in range(1, 172):
        if number != 162:
            (tmp_path / f"{number:04d}_synthetic.sql").write_text("-- synthetic\n")
    duplicate = tmp_path / "0018_another_historical.sql"
    duplicate.write_text("-- second historical migration\n")
    monkeypatch.setattr(runner, "SQL_ROOT", tmp_path)
    monkeypatch.setattr(runner, "BOOTSTRAP_THROUGH", 171)
    paths = runner._migration_paths()
    assert len(paths) == 171
    assert duplicate in paths
    assert paths == sorted(paths, key=lambda path: path.name)


@pytest.mark.parametrize("missing", [39, 168, 171])
def test_bootstrap_still_rejects_any_missing_required_migration(
    monkeypatch, tmp_path, missing
):
    import run_stage5d17_disposable_postgres_validation as runner

    for number in range(1, 172):
        if number not in (162, missing):
            (tmp_path / f"{number:04d}_synthetic.sql").write_text("-- synthetic\n")
    monkeypatch.setattr(runner, "SQL_ROOT", tmp_path)
    monkeypatch.setattr(runner, "BOOTSTRAP_THROUGH", 171)
    with pytest.raises(SystemExit):
        runner._migration_paths()
