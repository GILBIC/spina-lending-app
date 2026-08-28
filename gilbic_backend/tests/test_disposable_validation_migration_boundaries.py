from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQUIRED_7X7_OPERATIONAL_READER_MIGRATION = 107
REQUIRED_7X7_EXTRA_PRINCIPAL_BRIDGE_MIGRATION = 108
CURRENT_7X7_READER_VALIDATORS = (
    ROOT
    / "tools"
    / "run_7x7_source_event_accounting_preview_disposable_postgres_validation.py",
    ROOT
    / "tools"
    / "run_combined_collection_renewal_disposable_postgres_validation.py",
)
CURRENT_7X7_EXTRA_PRINCIPAL_BRIDGE_VALIDATORS = (
    ROOT / "tools" / "run_7x7_extra_principal_bridge_disposable_postgres_validation.py",
)
CURRENT_REMITTANCE_REPOSITORY_VALIDATORS = (
    ROOT / "tools" / "run_0102_remittance_review_disposable_postgres_validation.py",
)


def _bootstrap_through(path: Path) -> int:
    return _assigned_integer(path, "BOOTSTRAP_THROUGH")


def _assigned_integer(path: Path, assignment_name: str) -> int:
    if not path.is_file():
        raise AssertionError(f"Disposable validator is missing: {path}")

    module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == assignment_name
            for target in node.targets
        ):
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, int):
            return node.value.value
        raise AssertionError(
            f"{path} must assign {assignment_name} to an integer literal"
        )

    raise AssertionError(f"{path} must define {assignment_name}")


def test_current_7x7_reader_validators_include_required_migrations() -> None:
    stale: dict[str, int] = {}
    for path in CURRENT_7X7_READER_VALIDATORS:
        actual = _bootstrap_through(path)
        if actual < REQUIRED_7X7_OPERATIONAL_READER_MIGRATION:
            stale[path.relative_to(ROOT).as_posix()] = actual

    assert not stale, (
        "Current 7x7 reader validators must bootstrap through migration "
        f"{REQUIRED_7X7_OPERATIONAL_READER_MIGRATION:04d}: {stale}"
    )


def test_current_7x7_extra_principal_bridge_validators_include_required_migrations() -> (
    None
):
    stale: dict[str, int] = {}
    for path in CURRENT_7X7_EXTRA_PRINCIPAL_BRIDGE_VALIDATORS:
        actual = _bootstrap_through(path)
        if actual < REQUIRED_7X7_EXTRA_PRINCIPAL_BRIDGE_MIGRATION:
            stale[path.relative_to(ROOT).as_posix()] = actual

    assert not stale, (
        "Current 7x7 Extra Principal bridge validators must bootstrap through migration "
        f"{REQUIRED_7X7_EXTRA_PRINCIPAL_BRIDGE_MIGRATION:04d}: {stale}"
    )


def test_current_remittance_repository_validators_advance_to_bridge_schema() -> None:
    stale: dict[str, int] = {}
    for path in CURRENT_REMITTANCE_REPOSITORY_VALIDATORS:
        actual = _assigned_integer(path, "CURRENT_SCHEMA_THROUGH")
        if actual < REQUIRED_7X7_EXTRA_PRINCIPAL_BRIDGE_MIGRATION:
            stale[path.relative_to(ROOT).as_posix()] = actual

    assert not stale, (
        "Current remittance repository validators must advance through migration "
        f"{REQUIRED_7X7_EXTRA_PRINCIPAL_BRIDGE_MIGRATION:04d}: {stale}"
    )
