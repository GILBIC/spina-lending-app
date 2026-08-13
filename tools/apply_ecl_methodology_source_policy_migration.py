from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "gilbic_backend"
    / "sql"
    / "0069_add_ecl_methodology_source_policy.sql"
)


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _history_counts(connection: psycopg.Connection) -> tuple[int, int, int, int]:
    row = connection.execute(
        """
        SELECT
            (SELECT count(*) FROM accounting.ecl_historical_loan_episodes),
            (SELECT count(*) FROM accounting.ecl_outcome_label_reviews),
            (SELECT count(*) FROM accounting.journal_entries),
            (SELECT count(*) FROM accounting.journal_lines)
        """
    ).fetchone()
    return tuple(int(value) for value in row)


def _verify(connection: psycopg.Connection) -> tuple:
    objects = connection.execute(
        """
        SELECT
            to_regclass('accounting.ecl_methodology_policy_v1'),
            to_regclass('accounting.ecl_approved_source_classes_v1'),
            to_regclass('accounting.ecl_methodology_source_readiness')
        """
    ).fetchone()
    if any(item is None for item in objects):
        raise SystemExit("ECL methodology/source-policy verification failed: required views are missing")

    policy = connection.execute(
        """
        SELECT
            policy_version,
            methodology_approved,
            measurement_method,
            discount_rate_basis,
            pd_lgd_parameter_model_required,
            numeric_pd_enabled,
            numeric_lgd_enabled,
            numeric_cure_rate_enabled,
            numeric_recovery_rate_enabled,
            scenario_weights_enabled,
            automatic_staging_enabled,
            ecl_calculation_enabled,
            account_1190_posting_enabled,
            automatic_source_posting
        FROM accounting.ecl_methodology_policy_v1
        """
    ).fetchone()
    expected = (
        "ecl_methodology_v1",
        True,
        "probability_weighted_discounted_expected_cash_shortfall",
        "original_effective_interest_rate",
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
    )
    if policy != expected:
        raise SystemExit(f"ECL methodology/source-policy verification failed: policy mismatch {policy!r}")

    source_count = int(
        connection.execute(
            "SELECT count(*) FROM accounting.ecl_approved_source_classes_v1 WHERE approved_for_v1_methodology"
        ).fetchone()[0]
    )
    if source_count != 8:
        raise SystemExit(
            f"ECL methodology/source-policy verification failed: expected 8 approved source classes, found {source_count}"
        )

    readiness = connection.execute(
        """
        SELECT
            historical_episode_count,
            historical_structurally_usable_count,
            historical_source_review_required_count,
            historical_pending_outcome_review_count,
            historical_reviewed_outcome_count,
            historical_reviewed_default_count,
            historical_reviewed_non_default_count,
            methodology_source_status,
            methodology_policy_approved,
            protected_loss_recovery_evidence_ready,
            forward_looking_evidence_ready,
            staging_automation_enabled,
            quantitative_ecl_ready,
            ecl_calculation_enabled,
            account_1190_posting_enabled,
            automatic_source_posting
        FROM accounting.ecl_methodology_source_readiness
        """
    ).fetchone()
    if readiness is None:
        raise SystemExit("ECL methodology/source-policy verification failed: readiness row is missing")
    if not bool(readiness[8]):
        raise SystemExit("ECL methodology/source-policy verification failed: methodology is not approved")
    if any(bool(value) for value in readiness[9:]):
        raise SystemExit(
            "ECL methodology/source-policy verification failed: a quantitative, staging or posting gate was unexpectedly enabled"
        )
    return readiness


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Install and verify the view-only SPINA V1 ECL methodology/source policy on the approved live database."
        )
    )
    parser.add_argument("--env-file", action="append", type=Path, default=[])
    parser.add_argument("--database-url-env", default="GILBIC_DATABASE_URL")
    args = parser.parse_args()

    for env_path in args.env_file:
        _load_env_file(env_path)
    database_url = os.getenv(args.database_url_env)
    if not database_url:
        raise SystemExit(f"{args.database_url_env} is not configured")
    if not MIGRATION.is_file():
        raise SystemExit(f"ECL methodology/source-policy migration file was not found: {MIGRATION}")

    with psycopg.connect(database_url, autocommit=True) as connection:
        prerequisite = connection.execute(
            "SELECT to_regclass('accounting.ecl_outcome_label_review_summary')"
        ).fetchone()[0]
        if prerequisite is None:
            raise SystemExit(
                "ECL methodology/source-policy migration refused: Stage 5E.3 outcome-review foundation is not installed"
            )

        before = _history_counts(connection)
        connection.execute(MIGRATION.read_text(encoding="utf-8"))
        readiness = _verify(connection)
        after = _history_counts(connection)
        if after != before:
            raise SystemExit(
                f"ECL methodology/source-policy verification failed: protected history changed from {before} to {after}"
            )

    print(
        "ECL methodology/source-policy live summary: "
        f"episodes={readiness[0]}, usable={readiness[1]}, source_review={readiness[2]}, "
        f"pending_outcomes={readiness[3]}, reviewed={readiness[4]}, defaults={readiness[5]}, "
        f"non_defaults={readiness[6]}, status={readiness[7]}, history_unchanged=True, "
        "methodology_approved=True, protected_loss_recovery_evidence_ready=False, "
        "forward_looking_evidence_ready=False, staging_automation_enabled=False, "
        "quantitative_ecl_ready=False, ecl_calculation_enabled=False, "
        "account_1190_posting_enabled=False, automatic_source_posting=False."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
